from django.contrib import messages
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.htmx import hx_response, is_htmx
from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_get_object_or_404
from items.services import StackedPricingService
from ledger.coins import format_coins
from ledger.services import InsufficientItems, available_items
from player_characters import life
from player_characters.selection import selected_character
from quests import services
from quests.models import Quest, QuestCompletion
from quests.turnin import turnin_context


def _is_admin(request):
    return request.user.is_superuser or is_club_admin(request.user, request.club)


def _tilt(quest):
    """Fixed angle step -2..2 from the quest id: same on every load."""
    return quest.pk % 5 - 2


def _stamp(quest, have, counts, full):
    """'done', 'ready' or None for one quest and the selected character."""
    if quest.max_per_character is not None and counts.get(quest.pk, 0) >= quest.max_per_character:
        return "done"
    reqs = quest.requirements.all()
    if full or not reqs:
        return None
    if all(have.get(r.item_id, 0) >= r.quantity for r in reqs):
        return "ready"
    return None


def _progress(quest, have):
    """Per-requirement progress rows for a quest notice, or None when there are none."""
    reqs = quest.requirements.all()
    if not reqs:
        return None
    rows = []
    missing_total = 0
    for r in reqs:
        need = r.quantity
        have_n = have.get(r.item_id, 0)
        short = max(0, need - have_n)
        missing_total += short
        rows.append(
            {
                "item": r.item,
                "have": have_n,
                "need": need,
                "short": short,
                "percent": min(100, have_n * 100 // need) if need else 100,
                "unit_name": r.item.unit_name if r.item.is_stacked else "",
            }
        )
    return {"rows": rows, "missing_total": missing_total}


@club_member_required
def index(request, club_slug):
    today = timezone.localdate()
    is_admin = _is_admin(request)
    can_see_upcoming = is_admin or is_game_master(request.user, request.club)
    character = selected_character(request)
    have, counts = {}, {}
    if character is not None:
        have = available_items(character)
        counts = {
            row["quest"]: row["n"]
            for row in QuestCompletion.objects.filter(character=character)
            .values("quest")
            .annotate(n=Count("id"))
        }
    quests = (
        Quest.objects.for_club(request.club)
        .prefetch_related("requirements__item", "rewards__item")
        .annotate(done=Count("completions"))
    )
    board, taken_down = [], []
    for q in quests:
        q.left = None if q.max_completions is None else max(0, q.max_completions - q.done)
        q.tilt = _tilt(q)
        status = q.status_on(today)
        full = q.left == 0
        q.stamp = _stamp(q, have, counts, full) if character is not None else None
        if status == "live" and not full:
            q.progress = (
                _progress(q, have) if (character is not None and q.stamp != "done") else None
            )
            board.append(q)
            continue
        if status == "ended":
            q.notice_label = "Ended"
            q.notice_url = None
        elif status == "upcoming":
            if not can_see_upcoming:
                continue
            q.notice_label = "Not posted yet"
            q.notice_url = (
                reverse("quests:edit", args=[request.club.slug, q.pk]) if is_admin else None
            )
        else:
            q.notice_label = "Full"
            q.notice_url = reverse("quests:detail", args=[request.club.slug, q.pk])
        taken_down.append(q)
    celebration = request.session.pop("quest_celebration", None)
    if celebration and celebration.get("club") != request.club.slug:
        celebration = None
    return render(
        request,
        "quests/index.html",
        {
            "board": board,
            "taken_down": taken_down,
            "character": character,
            "is_admin": is_admin,
            "celebration": celebration,
        },
    )


@club_member_required
def detail(request, club_slug, pk):
    quest = club_get_object_or_404(request, Quest, pk=pk)
    if not quest.is_live_on(timezone.localdate()):
        raise Http404
    character = selected_character(request)
    club_left = services.completions_left(quest)
    row = None
    stamp = None
    turnin_rows = []
    rewards = quest.rewards.select_related("item")
    blocked_reason = None
    if character is not None:
        missing = services.missing_items(quest, character)
        left = services.character_completions_left(quest, character)
        context = turnin_context(quest, character)
        turnin_rows = context["turnin_rows"]
        rewards = context["rewards"]
        # Same order as quests.services.turn_in (liveness is checked above).
        reason = life.buy_block_reason(character)
        if reason:
            blocked_reason = reason
        elif not turnin_rows:
            blocked_reason = "This quest has no requirements."
        elif club_left == 0:
            blocked_reason = "This quest is full."
        elif left == 0:
            blocked_reason = f"{character} has completed this quest the maximum number of times."
        elif missing:
            blocked_reason = _missing_text(missing)
        row = {
            "missing": missing,
            "limit_reached": left == 0,
            "ready": blocked_reason is None,
        }
        if left == 0:
            stamp = "done"
        elif not missing and left != 0 and club_left != 0 and turnin_rows:
            stamp = "ready"
    quest.tilt = _tilt(quest)
    return render(
        request,
        "quests/play/detail.html",
        {
            "quest": quest,
            "requirements": quest.requirements.select_related("item"),
            "rewards": rewards,
            "character": character,
            "row": row,
            "turnin_rows": turnin_rows,
            "blocked_reason": blocked_reason,
            "stamp": stamp,
            "club_left": club_left,
            "is_admin": _is_admin(request),
        },
    )


def _missing_text(missing):
    return (
        "Missing "
        + ", ".join(StackedPricingService.unit_label(item, n) for item, n in missing)
        + "."
    )


def _reward_rows(quest):
    """Reward rows for the celebration fanfare: [{"symbol", "label"}, ...]."""
    rows = []
    for rw in quest.rewards.select_related("item"):
        if rw.coins > 0:
            rows.append({"symbol": "💰", "label": format_coins(rw.coins)})
        if rw.item_id and rw.quantity > 0:
            if rw.item.is_stacked:
                label = StackedPricingService.unit_label(rw.item, rw.quantity)
            else:
                label = f"{rw.quantity} {rw.item.name}"
            rows.append({"symbol": rw.item.symbol or "", "label": label})
    return rows


@club_member_required
@require_POST
def turn_in(request, club_slug, pk):
    quest = club_get_object_or_404(request, Quest, pk=pk)
    detail_url = redirect("quests:detail", club_slug=request.club.slug, pk=pk)
    character = selected_character(request)
    if character is None:
        messages.error(request, "You have no character in this club.")
        return detail_url

    # Reward rows for the celebration fanfare, built with the same wording
    # as the toast so the reward summary text is unchanged.
    rows = _reward_rows(quest)
    reward_summary = ", ".join(row["label"] for row in rows) if rows else "no reward"

    try:
        services.turn_in(quest, character, request.user)
    except InsufficientItems:
        messages.error(request, _missing_text(services.missing_items(quest, character)))
    except services.QuestNotLive as e:
        messages.error(request, str(e))
        return redirect("quests:index", club_slug=request.club.slug)
    except services.QuestError as e:
        messages.error(request, str(e))
    else:
        # Success!
        toast_message = f"✦ {character.name} completed {quest.name}! Reward: {reward_summary}"

        if rows:
            request.session["quest_celebration"] = {
                "club": request.club.slug,
                "quest": quest.name,
                "character": character.name,
                "rows": rows,
            }

        if is_htmx(request):
            # HTMX request: return 204 with HX-Redirect and HX-Trigger.
            # The 204 never swaps, so the HX-Trigger toast is lost on the
            # client-side redirect; add a Django toast message that shows
            # once the index loads.
            messages.success(request, toast_message, extra_tags="toast-success")
            return hx_response(
                redirect=reverse("quests:index", args=[club_slug]),
                trigger={
                    "toast": {"message": toast_message, "type": "success"},
                    "questCompleted": True,
                },
            )

        # Non-htmx: celebrate on the quest board index.
        messages.success(
            request, f"{character} completed {quest.name}.", extra_tags="toast-success"
        )
        return redirect("quests:index", club_slug=request.club.slug)
    return detail_url
