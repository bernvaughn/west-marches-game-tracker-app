"""Player dashboard view: contextual quick actions for between-session tasks."""

from collections import defaultdict

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from accounts.dashboard_providers import build_header_stats, get_provider, get_providers
from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_get_object_or_404
from downtime.models import DowntimePointEntry
from ledger.models import LedgerEntry
from player_characters.models import Character
from player_characters.selection import selected_character
from player_characters.sheet import xp_progress

# =============================================================================
# Dashboard Context Building (Uses Unified Provider System)
# =============================================================================


def _get_dashboard_context(request, club, character, membership):
    """Build the context dictionary for the player dashboard using providers."""
    header_provider = get_provider("header")
    header_ctx = {}
    if header_provider is not None:
        header_ctx = header_provider.get_context(request, club, character, membership)

    providers = []
    for provider in get_providers():
        if provider.key == "header":
            continue
        if provider.should_show(request, club, character, membership):
            ctx = provider.get_context(request, club, character, membership)
            providers.append(
                {
                    "key": provider.key,
                    "order": provider.order,
                    "template": provider.template,
                    "ctx": ctx,
                }
            )

    recent = _recent_awards(character)

    return {
        "character": character,
        "membership": membership,
        "dashboard_providers": providers,
        "xp_progress": xp_progress(character),
        "recent_awards": recent,
        **header_ctx,
    }


def _recent_awards(character, limit=5):
    """Merge ledger awards and downtime point awards for a character.

    Returns up to `limit` items, newest first, each a dict with keys:
    date, created, kind, coins, items, points, note.
    """
    ledger_entries = (
        LedgerEntry.objects.filter(
            character=character,
            kind__in=[
                LedgerEntry.Kind.AWARD,
                LedgerEntry.Kind.QUEST_REWARD,
                LedgerEntry.Kind.ADJUSTMENT,
                LedgerEntry.Kind.REVERSAL,
            ],
        )
        .prefetch_related("lines__item")
        .order_by("-date", "-id")[:limit]
    )

    downtime_entries = DowntimePointEntry.objects.filter(
        character=character,
        kind=DowntimePointEntry.Kind.AWARD,
    ).order_by("-date", "-id")[:limit]

    awards = []
    for entry in ledger_entries:
        coins = sum(line.coins for line in entry.lines.all())
        items = [
            (line.item.name, line.quantity)
            for line in entry.lines.all()
            if line.item_id and line.quantity
        ]
        awards.append(
            {
                "date": entry.date,
                "created": entry.created,
                "pk": entry.pk,
                "kind": "ledger",
                "coins": coins,
                "items": items,
                "points": None,
                "note": entry.note,
            }
        )

    for entry in downtime_entries:
        awards.append(
            {
                "date": entry.date,
                "created": entry.created,
                "pk": entry.pk,
                "kind": "downtime",
                "coins": 0,
                "items": [],
                "points": entry.delta,
                "note": entry.note,
            }
        )

    # Sort by (date, created, pk) descending; newest first.
    awards.sort(key=lambda a: (a["date"], a["created"], a["pk"]), reverse=True)

    return awards[:limit]


@club_member_required
def player_dashboard(request, club_slug):
    """Player dashboard with contextual quick actions for between-session tasks."""
    club = request.club
    membership = request.membership
    character = selected_character(request)

    # If user is GM or admin with no selected character, redirect to club home
    is_gm_or_admin = is_game_master(request.user, club) or is_club_admin(request.user, club)
    if is_gm_or_admin and character is None:
        return redirect("club_home", club_slug=club.slug)

    # If no character selected, show character selector prompt
    if character is None:
        return render(
            request,
            "accounts/dashboard_no_character.html",
            {
                "club": club,
                "membership": membership,
            },
        )

    ctx = _get_dashboard_context(request, club, character, membership)
    return render(request, "accounts/dashboard.html", ctx)


# =============================================================================
# HTMX Partial Endpoints
# =============================================================================


@club_member_required
def dashboard_partial(request, club_slug, provider_key):
    """HTMX partial endpoint for a dashboard provider."""
    club = request.club
    membership = request.membership
    character = selected_character(request)

    if character is None:
        raise Http404("No character selected.")

    provider = get_provider(provider_key)
    if provider is None:
        raise Http404(f"Provider '{provider_key}' not found.")

    if not provider.should_show(request, club, character, membership):
        raise Http404(f"Provider '{provider_key}' not available.")

    ctx = provider.get_context(request, club, character, membership)
    html = render_to_string(provider.template, {"provider_context": ctx}, request=request)
    return HttpResponse(html)


# =============================================================================
# Character Preview Endpoint
# =============================================================================


@club_member_required
def character_preview(request, club_slug, pk):
    """Character preview endpoint returning JSON for tooltip."""
    membership = request.membership
    character = club_get_object_or_404(request, Character, pk=pk)

    # Verify ownership
    if character.owner_id != membership.id:
        raise Http404("Not your character.")

    # Build preview data using shared helper
    stats = build_header_stats(character)

    return JsonResponse(
        {
            "name": character.name,
            "level": character.level,
            "char_class": character.char_class,
            "species": character.species,
            "coins_available": stats["coin_summary"].available,
            "junk_count": stats["junk_count"],
            "junk_value": stats["junk_value"],
            "downtime_balance": stats["downtime_balance"],
        }
    )


@club_member_required
def print_session_pack_modal(request, club_slug, pk):
    """HTMX partial endpoint for the Print Session Pack options modal."""
    character = club_get_object_or_404(request, Character, pk=pk)

    # Verify ownership
    if character.owner_id != request.membership.id:
        raise Http404("Not your character.")

    # Compute ledger diff since last print
    diff = _compute_print_diff(character)

    return render(
        request,
        "accounts/_print_session_pack_modal.html",
        {
            "club": request.club,
            "character": character,
            "diff": diff,
        },
    )


def _compute_print_diff(character):
    """Compute grouped summary of ledger changes since last_printed_at.

    Uses ``created`` (DateTimeField, auto_now_add) rather than ``date``
    (DateField) so entries created on the same day as the print do not
    reappear after printing. Backdated entries added after a print still
    show because their ``created`` timestamp is later than ``last_printed_at``.

    Returns a dict with keys:
    - 'first_print': bool (True if never printed before)
    - 'coins': int (net coin change in cp)
    - 'items': list of (item_name, net_qty) where net_qty != 0
    - 'quests': list of quest names completed
    - 'downtime': list of dict with 'action', 'coins', 'items' (list of (item_name, qty))
    """
    last_printed = character.last_printed_at
    if last_printed is None:
        entries = LedgerEntry.objects.filter(character=character).order_by("date", "id")
        first_print = True
    else:
        entries = LedgerEntry.objects.filter(
            character=character, created__gt=last_printed
        ).order_by("date", "id")
        first_print = False

    if not entries:
        return {
            "first_print": first_print,
            "coins": 0,
            "items": [],
            "quests": [],
            "downtime": [],
        }

    coins_net = 0
    items_net = defaultdict(int)
    quests_completed = set()
    downtime_rewards = []

    for entry in entries:
        lines = entry.lines.select_related("item")
        if entry.kind in (LedgerEntry.Kind.QUEST_TURN_IN, LedgerEntry.Kind.QUEST_REWARD):
            # Quest entries: extract quest name from note
            # Note format: "Turned in for quest {name}" or "Reward for quest {name}"
            if entry.note:
                if "quest " in entry.note.lower():
                    # Extract quest name after "quest "
                    parts = entry.note.split("quest ", 1)
                    if len(parts) > 1:
                        quest_name = parts[1].strip()
                        quests_completed.add(quest_name)
            # Skip coins/items from quest entries to avoid double-counting
            continue
        elif (
            entry.kind == LedgerEntry.Kind.AWARD
            and entry.note
            and entry.note.startswith("Downtime: ")
        ):
            # Downtime award: record separately
            action_name = entry.note[len("Downtime: ") :].strip()
            downtime_coins = 0
            downtime_items = []
            for line in lines:
                if line.coins:
                    downtime_coins += line.coins
                if line.item_id and line.quantity:
                    downtime_items.append((line.item.name, line.quantity))
            downtime_rewards.append(
                {
                    "action": action_name,
                    "coins": downtime_coins,
                    "items": downtime_items,
                }
            )
            # Skip coins/items from downtime entries to avoid double-counting
            continue
        # All other entries: aggregate coins and items
        for line in lines:
            if line.coins:
                coins_net += line.coins
            if line.item_id and line.quantity:
                items_net[line.item.name] += line.quantity

    # Filter out zero-net items
    items_list = [(name, qty) for name, qty in items_net.items() if qty != 0]
    items_list.sort(key=lambda x: x[0])

    return {
        "first_print": first_print,
        "coins": coins_net,
        "items": items_list,
        "quests": sorted(quests_completed),
        "downtime": downtime_rewards,
    }
