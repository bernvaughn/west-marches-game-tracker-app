"""""Player dashboard view: contextual quick actions for between-session tasks."""

from ledger.coins import format_coins

from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_queryset
from downtime import services as downtime_services
from downtime.models import DowntimeAction
from ledger.services import coin_balance, available_items
from map.models import HexMap
from player_characters.inventory import coin_summary, inventory_rows
from player_characters.junk import junk_rows, junk_value
from player_characters.models import Character, Trade
from player_characters.selection import selected_character
from player_characters.trade_services import OPEN
from quests.models import Quest, QuestCompletion


def _get_dashboard_context(request, club, character, membership):
    """Build the context dictionary for the player dashboard."""
    today = timezone.localdate()

    # --- Character summary ---
    coin_sum = coin_summary(character)
    downtime_balance = downtime_services.balance(character)
    junk = junk_rows(character)
    junk_val = junk_value(character, junk)

    # --- Open trades ---
    trades_qs = club_queryset(request, Trade).filter(status__in=OPEN)
    my_trades = trades_qs.filter(
        Q(sender__owner=membership) | Q(receiver__owner=membership)
    ).select_related("sender__owner__user", "receiver__owner__user")

    open_trades_data = []
    for t in my_trades:
        if t.sender.owner_id == membership.id:
            other = t.receiver
            side = "sender"
        else:
            other = t.sender
            side = "receiver"
        open_trades_data.append({
            "trade": t,
            "other_character": other,
            "side": side,
            "status_display": t.get_status_display(),
        })

    # --- Quests: live, not full, check if ready to turn in ---
    quests_qs = Quest.objects.for_club(club).prefetch_related(
        "requirements__item", "rewards__item"
    ).annotate(done=Count("completions"))

    have = available_items(character)
    my_completions = {
        row["quest"]: row["n"]
        for row in QuestCompletion.objects.filter(character=character)
        .values("quest")
        .annotate(n=Count("id"))
    }

    ready_quests = []
    for q in quests_qs:
        if not q.is_live_on(today):
            continue
        if q.max_completions is not None and q.done >= q.max_completions:
            continue
        if q.max_per_character is not None and my_completions.get(q.pk, 0) >= q.max_per_character:
            continue
        reqs = list(q.requirements.all())
        if reqs and all(have.get(r.item_id, 0) >= r.quantity for r in reqs):
            ready_quests.append(q)

    # --- Downtime: live actions with entries ---
    live_actions = (
        DowntimeAction.objects.for_club(club)
        .live_on(today)
        .filter(entries__isnull=False)
        .distinct()
        .prefetch_related("entries__items__item")
    )

    downtime_cards = []
    for action in live_actions:
        reason = ""
        if downtime_balance < action.cost:
            reason = "Not enough downtime points."
        downtime_cards.append({
            "action": action,
            "cost": action.cost,
            "reason": reason,
        })

    # --- Map: visible maps ---
    maps = HexMap.objects.for_club(club).order_by("name")

    # --- Unread messages count ---
    from accounts.models import Message
    unread_count = Message.objects.for_club(club).filter(
        status=Message.Status.OPEN
    ).exclude(sender=membership).count()

    # Build action items for each section
    from django.urls import reverse

    junk_val_formatted = format_coins(junk_val)

    town_items = [
        {
            "label": "Shop Street",
            "url": reverse("shops:index", args=[club.slug]),
            "icon": "shop",
            "subtext": "Browse open shops & sell junk",
        },
    ]

    quest_items = []
    for q in ready_quests:
        quest_items.append({
            "label": q.name,
            "url": reverse("quests:detail", args=[club.slug, q.pk]),
            "icon": "check-circle",
            "subtext": "Ready to turn in",
        })
    if not quest_items:
        quest_items.append({
            "label": "Quest Board",
            "url": reverse("quests:index", args=[club.slug]),
            "icon": "scroll",
            "subtext": "Browse available quests",
        })

    trade_items = []
    for t in open_trades_data:
        trade_items.append({
            "label": f"Trade with {t['other_character'].name}",
            "url": reverse("trades:detail", args=[club.slug, t['trade'].pk]),
            "icon": "arrow-left-right",
            "subtext": t['status_display'],
        })
    if not trade_items:
        trade_items.append({
            "label": "Propose Trade",
            "url": reverse("trades:propose", args=[club.slug]),
            "icon": "plus",
            "subtext": "Start a new trade",
        })

    downtime_items = []
    for d in downtime_cards:
        downtime_items.append({
            "label": d["action"].name,
            "url": reverse("downtime:play", args=[club.slug]),
            "icon": "clock",
            "subtext": f"Cost: {d['cost']} point{'s' if d['cost'] != 1 else ''}",
            "badge": "" if not d["reason"] else "disabled",
        })
    if not downtime_items:
        downtime_items.append({
            "label": "Downtime Actions",
            "url": reverse("downtime:play", args=[club.slug]),
            "icon": "clock",
            "subtext": "No actions available",
        })

    map_items = [
        {
            "label": m.name,
            "url": reverse("map:detail", args=[club.slug, m.pk]),
            "icon": "map",
            "subtext": "View map",
        }
        for m in maps
    ]
    if not map_items:
        map_items.append({
            "label": "Map",
            "url": reverse("map:index", args=[club.slug]),
            "icon": "map",
            "subtext": "No maps yet",
        })

    # Players can only message admins, not view inbox
    message_items = [
        {
            "label": "Message Admins",
            "url": reverse("accounts:message_new", args=[club.slug]),
            "icon": "pencil",
            "subtext": "Send a message to club admins",
        },
    ]

    return {
        "character": character,
        "coin_summary": coin_sum,
        "downtime_balance": downtime_balance,
        "junk_count": len(junk),
        "junk_value": junk_val,
        "open_trades": open_trades_data,
        "ready_quests": ready_quests,
        "downtime_cards": downtime_cards,
        "maps": maps,
        "unread_count": unread_count,
        "membership": membership,
        "town_items": town_items,
        "quest_items": quest_items,
        "trade_items": trade_items,
        "downtime_items": downtime_items,
        "map_items": map_items,
        "message_items": message_items,
    }


@club_member_required
def player_dashboard(request, club_slug):
    """Player dashboard with contextual quick actions for between-session tasks."""
    club = request.club
    membership = request.membership
    character = selected_character(request)

    # If user is GM or admin, redirect to club home (navigation cards)
    if is_game_master(request.user, club) or is_club_admin(request.user, club):
        from django.shortcuts import redirect
        return redirect("club_home", club_slug=club.slug)

    # If no character selected, show character selector prompt
    if character is None:
        return render(request, "accounts/dashboard_no_character.html", {
            "club": club,
            "membership": membership,
        })

    ctx = _get_dashboard_context(request, club, character, membership)
    return render(request, "accounts/dashboard.html", ctx)