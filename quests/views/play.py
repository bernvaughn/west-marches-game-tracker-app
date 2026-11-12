from django.contrib import messages
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_get_object_or_404
from ledger.services import InsufficientItems, available_items
from player_characters.selection import selected_character
from quests import services
from quests.models import Quest, QuestCompletion


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
    return render(
        request,
        "quests/index.html",
        {
            "board": board,
            "taken_down": taken_down,
            "character": character,
            "is_admin": is_admin,
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
    blocked_reason = None
    if character is not None:
        have = available_items(character)
        missing = services.missing_items(quest, character)
        left = services.character_completions_left(quest, character)
        for req in quest.requirements.select_related("item"):
            has = have.get(req.item_id, 0)
            turnin_rows.append(
                {
                    "item": req.item,
                    "needed": req.quantity,
                    "has": has,
                    "short": max(0, req.quantity - has),
                }
            )
        # Same order as quests.services.turn_in (liveness is checked above).
        if not turnin_rows:
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
            "rewards": quest.rewards.select_related("item"),
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
    return "Missing " + ", ".join(f"{n} x {item}" for item, n in missing) + "."


@club_member_required
@require_POST
def turn_in(request, club_slug, pk):
    quest = club_get_object_or_404(request, Quest, pk=pk)
    detail_url = redirect("quests:detail", club_slug=request.club.slug, pk=pk)
    character = selected_character(request)
    if character is None:
        messages.error(request, "You have no character in this club.")
        return detail_url
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
        messages.success(request, f"{character} completed {quest.name}.")
    return detail_url
