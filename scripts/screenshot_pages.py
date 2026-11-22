"""The page list for the screenshot tool and its smoke test.

This module has no Playwright import. It needs Django to be set up.
Each `Page` names a demo role, a URL and an optional browser action.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

from django.urls import reverse

ROLES = {
    "anon": None,
    "site_admin": "admin@example.com",
    "gm": "gm@example.com",
    "alice": "alice@example.com",
    "bob": "bob@example.com",
    # Created by `extra_fixtures()`, not `seed_demo`.
    "gm_only": "gm-only@example.com",  # game master, not club admin
    "club_admin": "clubadmin@example.com",  # club admin, not game master
}
BOTH = (1280, 390)
# Click targets for the modal actions. `screenshots._act` reads this; it has no Playwright import.
MODAL_SELECTORS = {
    "buy_modal": "a[data-app-modal]",
    "tile_modal": "svg a[data-app-modal]",
    "grant_modal": 'a[data-app-modal][href*="/give/coins/"]',
    "sell_junk_modal": 'a[data-app-modal][href*="/sell-junk/"]',
    "junk_modal": 'a[data-app-modal][href*="/junk/"]',
    "note_modal": 'a[data-app-modal][href*="/note/"]',
    "consume_modal": 'a[data-app-modal][href*="/consume/"]',
    "stall_buy_modal": 'a[data-app-modal][href*="/stall/"]',
    "give_items_modal": 'a[data-app-modal][href*="/give/items/"]',
    "status_modal": 'a[data-app-modal][href*="/status/"]',
    "where_to_buy_modal": 'a[data-app-modal][href*="/where-to-buy/"]',
    "details_modal": 'a[data-app-modal][href*="/details-modal/"]',
    "agenda_add_modal": "a.agenda-plus[data-app-modal]",
    "print_session_pack_modal": 'a[data-app-modal][href*="print-session-pack-modal/"]',
    "roles_modal": 'a[data-app-modal][href*="/roles/"]',
}
# `sell_modal` submits a form (the confirm modal comes from a POST), so it has no link selector.
MODAL_ACTIONS = set(MODAL_SELECTORS) | {"sell_modal"}


@dataclass(frozen=True)
class Page:
    name: str
    role: str
    url: Callable[[SimpleNamespace], str]
    action: str | None = None
    widths: tuple[int, ...] = BOTH
    # Widths for `--audit` and `--widths`. None means every chosen width.
    audit_widths: tuple[int, ...] | None = None
    # For modal actions: the fragment URL that the smoke test fetches with HX-Request.
    modal_url: Callable[[SimpleNamespace], str] | None = None


def _role_users(club):
    """A game master who is not a club admin, and a club admin who is not a game master."""
    from accounts.demo import _user
    from accounts.models import Membership

    for email, name, gm, admin in (
        ("gm-only@example.com", "Gale the Game Master", True, False),
        ("clubadmin@example.com", "Cleo the Club Admin", False, True),
    ):
        Membership.objects.get_or_create(
            user=_user(email, name),
            club=club,
            defaults={"is_game_master": gm, "is_club_admin": admin},
        )


def _junk(aria):
    """Aria sets aside one of her five torches, so the sell-junk page has a row."""
    from items.models import Item
    from player_characters.models import JunkMark

    torch = Item.objects.filter(club=aria.club, name="Torch").first()
    if torch:
        JunkMark.objects.get_or_create(character=aria, item=torch, defaults={"quantity": 1})


def _point_request(club, aria):
    from accounts.models import Membership
    from downtime.models import DowntimePointRequest

    alice = Membership.objects.get(user__email="alice@example.com", club=club)
    note = "We cleared the goblin cave together."
    if not DowntimePointRequest.objects.filter(club=club, note=note).exists():
        request = DowntimePointRequest.objects.create(
            club=club, requested_by=alice, points=2, note=note
        )
        request.characters.add(aria)


def _downtime_result(aria):
    """A past bakery result. Made directly, so Aria's points and ledger stay as seeded."""
    from downtime.models import DowntimeAction, DowntimeResult

    action = DowntimeAction.objects.filter(club=aria.club, name="Work at a bakery").first()
    entry = action.entries.first() if action else None
    if entry:
        DowntimeResult.objects.get_or_create(
            character=aria, action=action, defaults={"entry": entry}
        )


def _play_session(club):
    """A game night next week, run by the demo game master."""
    from datetime import timedelta

    from django.utils import timezone

    from accounts.models import Membership
    from play_sessions.models import PlaySession

    gm = Membership.objects.filter(club=club, user__email="gm@example.com").first()
    PlaySession.objects.get_or_create(
        club=club,
        title="Return to the Wolf Den",
        defaults={
            "starts_at": timezone.now() + timedelta(days=7),
            "ends_at": timezone.now() + timedelta(days=7, hours=3),
            "game_master": gm,
            "location": "The back room of The Rusty Lantern",
            "notes": "Bring torches. We meet at the gate.",
        },
    )


def extra_fixtures():
    """Add objects that `seed_demo` lacks. Safe to run twice.

    Each helper is a `get_or_create`, so a second run changes nothing.
    """
    from accounts.models import Club
    from player_characters.models import Character

    club = Club.objects.get(slug="demo")
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    _role_users(club)
    _junk(aria)
    _point_request(club, aria)
    _downtime_result(aria)
    _play_session(club)


def demo_objects() -> SimpleNamespace:
    from accounts.models import Club, Membership, Message
    from agent_access.models import ProposedBatch, ProposedItem
    from downtime.models import DowntimeAction, DowntimePointRequest, DowntimeResult
    from items.models import Item
    from ledger.services import available_items
    from map.models import Encounter, HexMap, Location, MapRequest
    from play_sessions.models import PlaySession
    from player_characters.models import Character
    from quests.models import Quest
    from shops.models import Rotation, Shop, ShopStock

    club = Club.objects.get(slug="demo")
    batch = ProposedBatch.objects.get(idempotency_key="demo-session-1")
    wolf_den = Location.objects.get(name="Wolf Den")
    caravan = Shop.objects.get(name="Wandering Caravan")
    aria = Character.objects.get(name="Aria Windrunner")
    owned_item = Item.objects.filter(
        pk__in=[i for i, q in available_items(aria).items() if q > 0]
    ).first()
    play_session = PlaySession.objects.filter(club=club).first()
    return SimpleNamespace(
        owned_item=owned_item,
        club=club,
        slug=club.slug,
        aria=Character.objects.get(name="Aria Windrunner"),
        borin=Character.objects.get(name="Borin Stonefist"),
        lantern=Shop.objects.get(name="The Rusty Lantern"),
        caravan=caravan,
        stock=ShopStock.objects.filter(shop=caravan).first(),
        rotation=Rotation.objects.first(),
        quest=Quest.objects.get(name="Pelts for the Tanner"),
        map=HexMap.objects.get(name="The Marches"),
        location=wolf_den,
        watchtower=Location.objects.get(name="Old Watchtower"),
        encounter=Encounter.objects.filter(location=wolf_den).first(),
        batch=batch,
        line=batch.lines.first(),
        proposed_item=ProposedItem.objects.first(),
        message=Message.objects.filter(kind=Message.Kind.MESSAGE).first(),
        alice_membership=Membership.objects.get(user__email="alice@example.com", club=club),
        map_request=MapRequest.objects.first(),
        item=Item.objects.filter(club=club).order_by("name").first(),
        torch=Item.objects.get(club=club, name="Torch"),
        result=DowntimeResult.objects.first(),
        point_request=DowntimePointRequest.objects.first(),
        bakery=DowntimeAction.objects.get(club=club, name="Work at a bakery"),
        play_session=play_session,
    )


EXCLUDED = {
    "favicon": "An icon file, not a page.",
    "healthz": "A health check endpoint returning plain text, not a page.",
    "logout": "POST only.",
    "starting_equipment:templates": "Placeholder view for starting equipment (implemented in SE3).",
    "starting_equipment:template_create": "Stub view, Template CRUD child task.",
    "starting_equipment:template_detail": "Stub view, Template CRUD child task.",
    "starting_equipment:template_edit": "Stub view, Template CRUD child task.",
    "starting_equipment:template_delete": "Stub view, Template CRUD child task.",
    "starting_equipment:template_set_active": "Stub view, Template CRUD child task.",
    "starting_equipment:class_entry_list": "Stub view, Entry Mgmt child task.",
    "starting_equipment:class_entry_create": "Stub view, Entry Mgmt child task.",
    "starting_equipment:class_entry_edit": "Stub view, Entry Mgmt child task.",
    "starting_equipment:class_entry_delete": "Stub view, Entry Mgmt child task.",
    "starting_equipment:background_entry_list": "Stub view, Entry Mgmt child task.",
    "starting_equipment:background_entry_create": "Stub view, Entry Mgmt child task.",
    "starting_equipment:background_entry_edit": "Stub view, Entry Mgmt child task.",
    "starting_equipment:background_entry_delete": "Stub view, Entry Mgmt child task.",
    "starting_equipment:level_coins_list": "Stub view, Entry Mgmt child task.",
    "starting_equipment:level_coins_create": "Stub view, Entry Mgmt child task.",
    "starting_equipment:level_coins_edit": "Stub view, Entry Mgmt child task.",
    "starting_equipment:level_coins_delete": "Stub view, Entry Mgmt child task.",
    "starting_equipment:magic_option_list": "Stub view, Entry Mgmt child task.",
    "starting_equipment:magic_option_create": "Stub view, Entry Mgmt child task.",
    "starting_equipment:magic_option_edit": "Stub view, Entry Mgmt child task.",
    "starting_equipment:magic_option_delete": "Stub view, Entry Mgmt child task.",
    "starting_equipment:claim": "POST only; claim starting equipment for a character.",
    "starting_equipment:choices": (
        "GET picker page; needs an unclaimed character with choice groups (demo state varies)."
    ),
    "characters:starting_reveal": (
        "Needs a character with a granted 'Starting equipment' entry (demo state varies)."
    ),
    "starting_equipment:request_decide": "POST only; admin/GM approve or decline.",
    "starting_equipment:request_decide_confirm": "HTMX confirm modal; needs a starting request PK.",
    "starting_equipment:request_status": "HTMX partial for a request status row.",
    "mcp": "A JSON-RPC endpoint, not a page.",
    "oauth2_provider:oauth-server-metadata": "A JSON metadata document.",
    "oauth2_provider:oauth-resource-metadata": "A JSON metadata document.",
    "oauth2_provider:oauth-resource-metadata-path": "A JSON metadata document.",
    "oauth2_provider:authorize": "Needs a registered OAuth client and PKCE parameters.",
    "oauth2_provider:token": "A JSON API.",
    "oauth2_provider:revoke-token": "A JSON API.",
    "oauth2_provider:dcr-register": "A JSON API.",
    "oauth2_provider:dcr-register-management": "A JSON API.",
    "accounts:message_status": "POST only.",
    "accounts:message_bulk_status": "POST only.",
    "site_feedback_status": "POST only; site admin changes a report's status.",
    "characters:open_container": "POST only; opens a container from the character sheet via htmx.",
    "characters:select": "POST only.",
    "characters:shop_toggle": "POST only.",
    "characters:preview": "JSON endpoint for tooltip preview, not a page.",
    "items:retire": "POST only.",
    "items:restore": "POST only.",
    "items:delete": "POST only.",
    "items:convert": "Conversion preview/confirm page for stacked items (POST with confirm).",
    "shops:street_settings": "POST only.",
    "shops:stock_remove": "POST only.",
    "shops:rotation_delete": "POST only.",
    "shops:sell_item": "GET redirects to the shop; `shops-sell-modal` captures the confirm modal.",
    "shops:stock_fragment": "An htmx partial with no layout; `shops-detail-*` shows it.",
    "shops:favorite_toggle": "POST only; htmx endpoint for favorite toggle.",
    "shops:stall_favorite_toggle": "POST only; htmx endpoint for stall favorite toggle.",
    "map:request_approve": "POST only.",
    "map:request_decline": "POST only.",
    "map:request_bulk_approve": (
        "HTMX modal endpoint requiring `?requests=` IDs; opened from `map-requests`."
    ),
    "quests:turn_in": "POST only; turn-in is an inline form on `quests-detail`.",
    "quests:delete": "POST only.",
    "downtime:spend": "POST only.",
    "downtime:request_approve": "POST only.",
    "downtime:request_decline": "POST only.",
    "agent_access:connection_revoke": "POST only.",
    "agent_access:batch_confirm": "POST only.",
    "agent_access:batch_discard": "POST only.",
    "agent_access:batch_line_edit": "POST only.",
    "agent_access:batch_line_remove": "POST only.",
    "agent_access:batch_reverse": "POST only.",
    "agent_access:proposed_item_approve": "POST only.",
    "agent_access:proposed_item_reject": "POST only.",
    "accounts:quick_action_sell_junk": "HTMX partial endpoint for sell junk modal.",
    "accounts:quick_action_buy_potions": "HTMX partial endpoint for buy potions modal.",
    "accounts:character_preview": "HTMX partial (JSON), not a page.",
    "accounts:dashboard_partial": "HTMX partial, not a page.",
    "accounts:dashboard_downtime_spend": "HTMX partial endpoint for downtime spend wheel modal.",
    "accounts:dashboard_quest_turnin": "HTMX partial endpoint for quest turn-in modal.",
    "accounts:consumable_consume_partial": "HTMX partial endpoint for consumable confirm modal.",
    "shops:sell_junk_pick": "HTMX partial endpoint for shop picker modal.",
    "characters:bulk_award": "GM-only page for bulk awarding loot to multiple characters.",
    "accounts:message_detail": "Read-only message detail page; requires specific message PK.",
    # C1 death and archive stub views
    "characters:death": "C1 stub view returning 404.",
    "characters:death_undo": "C1 stub view returning 404.",
    "characters:archive": "C1 stub view returning 404.",
    "characters:unarchive": "C1 stub view returning 404.",
    "characters:archived": "C1 stub view returning 404.",
    "characters:fallen": "C1 stub view returning 404.",
    # character_options - admin only, HTMX modals
    "character_options:index": "Admin redirect to species list.",
    "character_options:list": "Admin list with HTMX partials; modals are separate.",
    "character_options:create": "Admin create modal; POST only for non-HTMX.",
    "character_options:edit": "Admin edit modal; POST only for non-HTMX.",
    "character_options:archive": "POST only.",
    "character_options:restore": "POST only.",
    "character_options:delete": "GET shows confirm modal; POST deletes.",
    "character_options:move": "POST only.",
    # Play session attendance URLs require a session PK and club context
    "play_sessions:attendance": "Attendance page; requires session PK and club context.",
    "play_sessions:rsvp_for": "POST-only RSVP override; requires session PK and club context.",
}


def _c(name, *args):
    """A club-scoped URL builder: reverse(name, [slug, *attrs of demo])."""

    def build(d):
        return reverse(name, args=[d.slug, *[_get(d, a) for a in args]])

    return build


def _get(d, path):
    obj = d
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _tile(d):
    t = d.location.tile
    return reverse("map:tile", args=[d.slug, d.map.pk, t.q, t.r])


def _build_pages() -> list[Page]:
    P = Page
    pages = [
        P("login", "anon", lambda d: reverse("login")),
        P("about", "anon", lambda d: reverse("about")),
        P("plans", "anon", lambda d: reverse("plans")),
        P("home-alice", "alice", lambda d: reverse("home")),
        P("home-site-admin", "site_admin", lambda d: reverse("home")),
        P("password-change", "alice", lambda d: reverse("password_change")),
        P("club-home-alice", "alice", lambda d: reverse("club_home", args=[d.slug])),
        P("club-home-gm", "gm", lambda d: reverse("club_home", args=[d.slug])),
        P(
            "topbar-menu-open",
            "alice",
            lambda d: reverse("club_home", args=[d.slug]),
            action="menu_open",
            widths=(390,),
            audit_widths=(768, 390),  # the toggler only shows below 992 px
        ),
        # accounts
        P("accounts-index", "gm", _c("accounts:index")),
        P("accounts-whitelist", "gm", _c("accounts:whitelist")),
        P("accounts-reset-password", "gm", _c("accounts:reset_password", "alice_membership.pk")),
        P("accounts-message-new", "alice", _c("accounts:message_new")),
        P("accounts-stock-request-new", "alice", _c("accounts:stock_request_new")),
        P("accounts-message-inbox", "gm", _c("accounts:message_inbox")),
        P("accounts-message-grant", "gm", _c("accounts:message_give_coins", "message.pk")),
        P(
            "inbox-grant-modal",
            "gm",
            _c("accounts:message_inbox"),
            action="grant_modal",
            modal_url=_c("accounts:message_give_coins", "message.pk"),
        ),
        # site admin
        P("site-clubs", "site_admin", lambda d: reverse("site_clubs")),
        P("site-club-new", "site_admin", lambda d: reverse("site_club_new")),
        P("site-settings", "site_admin", lambda d: reverse("site_settings")),
        P("site-design", "site_admin", lambda d: reverse("site_design")),
        P("site-feedback", "site_admin", lambda d: reverse("site_feedback")),
        P("site-feedback-new", "alice", lambda d: reverse("feedback_new")),
        # characters
        P("characters-directory-alice", "alice", _c("characters:directory")),
        P("characters-index-gm", "gm", _c("characters:index")),
        P("characters-create", "alice", _c("characters:create")),
        P("characters-slips-gm", "gm", _c("characters:slips")),
        P("characters-slips-alice", "alice", _c("characters:slips")),
        P("characters-detail-alice", "alice", _c("characters:detail", "aria.pk")),
        P("characters-detail-gm", "gm", _c("characters:detail", "aria.pk")),
        P("characters-edit", "alice", _c("characters:edit", "aria.pk")),
        P("characters-handover", "gm", _c("characters:handover", "aria.pk")),
        P("characters-adjust", "gm", _c("characters:adjust", "aria.pk")),
        P("characters-consume", "gm", _c("characters:consume", "aria.pk")),
        P(
            "characters-consume-player",
            "alice",
            _c("characters:player_consume", "aria.pk", "owned_item.pk"),
        ),
        P("characters-print-items", "alice", _c("characters:print_items", "aria.pk")),
        P("characters-print-session-pack", "alice", _c("characters:print_session_pack", "aria.pk")),
        # downtime
        P("downtime-play", "alice", lambda d: reverse("downtime:play", args=[d.slug])),
        P("downtime-actions", "gm", lambda d: reverse("downtime:actions", args=[d.slug])),
        P("downtime-action-new", "gm", lambda d: reverse("downtime:action_new", args=[d.slug])),
        # items
        P("items-index", "alice", _c("items:index")),
        P("items-index-gm", "gm", _c("items:index")),
        P("items-create", "gm", _c("items:create")),
        P("items-detail", "alice", _c("items:detail", "item.pk")),
        P("items-where-to-buy", "alice", _c("items:where_to_buy", "item.pk")),
        P("items-edit", "gm", _c("items:edit", "item.pk")),
        P("items-loot-cards-picker", "gm", _c("items:loot_cards_picker")),
        P(
            "items-loot-cards-print",
            "gm",
            lambda d: reverse("items:loot_cards_print", args=[d.slug]) + f"?qty_{d.item.pk}=1",
        ),
        # downtime agenda
        P("downtime-agenda", "gm", _c("downtime:agenda")),
        P("downtime-agenda-action-new", "gm", _c("downtime:agenda_action_create")),
        # shops
        P("shops-index", "alice", _c("shops:index")),
        P("shops-detail-lantern", "alice", _c("shops:detail", "lantern.pk")),
        P("shops-detail-caravan", "alice", _c("shops:detail", "caravan.pk")),
        P("shops-buy", "alice", _c("shops:buy", "caravan.pk", "stock.pk")),
        P(
            "shops-buy-modal",
            "alice",
            _c("shops:detail", "caravan.pk"),
            action="buy_modal",
            modal_url=_c("shops:buy", "caravan.pk", "stock.pk"),
        ),
        P("shops-manage-list", "gm", _c("shops:manage_list")),
        P("shops-manage-create", "gm", _c("shops:manage_create")),
        P("shops-manage-edit", "gm", _c("shops:manage_edit", "caravan.pk")),
        P("shops-stock-add", "gm", _c("shops:stock_add", "caravan.pk")),
        P("shops-stock-edit", "gm", _c("shops:stock_edit", "caravan.pk", "stock.pk")),
        P("shops-rotation-list", "gm", _c("shops:rotation_list")),
        P("shops-rotation-create", "gm", _c("shops:rotation_create")),
        P("shops-rotation-edit", "gm", _c("shops:rotation_edit", "rotation.pk")),
        P(
            "shops-rotation-copy-stock",
            "gm",
            _c("shops:rotation_copy_stock", "rotation.pk"),
        ),
        # ledger
        P("ledger-index", "gm", _c("ledger:index")),
        P("ledger-character-history", "alice", _c("ledger:character_history", "aria.pk")),
        # starting equipment
        P(
            "starting-equipment-request-new",
            "alice",
            _c("starting_equipment:request_new", "aria.pk"),
        ),
        # map
        P("map-index-alice", "alice", _c("map:index")),
        P("map-index-gm", "gm", _c("map:index")),
        P("map-detail-alice", "alice", _c("map:detail", "map.pk")),
        P("map-detail-gm", "gm", _c("map:detail", "map.pk")),
        P("map-tile", "alice", _tile),
        P(
            "map-tile-modal",
            "alice",
            _c("map:detail", "map.pk"),
            action="tile_modal",
            modal_url=_tile,
        ),
        P("map-create", "gm", _c("map:map_create")),
        P("map-edit", "gm", _c("map:map_edit", "map.pk")),
        P(
            "map-location-create",
            "gm",
            lambda d: reverse("map:location_create", args=[d.slug, d.map.pk, 2, 0]),
        ),
        P("map-location-edit", "gm", _c("map:location_edit", "location.pk")),
        P("map-location-delete", "gm", _c("map:location_delete", "location.pk")),
        P("map-encounter-create", "gm", _c("map:encounter_create", "location.pk")),
        P("map-encounter-edit", "gm", _c("map:encounter_edit", "encounter.pk")),
        P("map-encounter-delete", "gm", _c("map:encounter_delete", "encounter.pk")),
        P("map-requests", "gm", _c("map:requests")),
        P("map-request-visit", "alice", _c("map:request_visit", "map.pk")),
        P(
            "map-request-credit",
            "alice",
            lambda d: reverse("map:request_credit", args=[d.slug, "discovered", d.watchtower.pk]),
        ),
        P("map-xp", "alice", _c("map:xp")),
        P("map-print", "alice", _c("map:print", "map.pk")),
        # quests
        P("quests-index", "alice", _c("quests:index")),
        P("quests-detail", "alice", _c("quests:detail", "quest.pk")),
        P("quests-manage", "gm", _c("quests:manage")),
        P("quests-create", "gm", _c("quests:create")),
        P("quests-edit", "gm", _c("quests:edit", "quest.pk")),
        # agent access
        P("agent-index", "gm", _c("agent_access:index")),
        P("agent-connections", "gm", _c("agent_access:connections")),
        P("agent-batches", "gm", _c("agent_access:batches")),
        P("agent-batch-detail", "gm", _c("agent_access:batch_detail", "batch.pk")),
        P("agent-proposed-items", "gm", _c("agent_access:proposed_items")),
        P(
            "agent-proposed-item-detail",
            "gm",
            _c("agent_access:proposed_item_detail", "proposed_item.pk"),
        ),
        # --- Added for the U84 audit: every other GET page, and role variants ---
        # auth
        P("password-change-done", "alice", lambda d: reverse("password_change_done")),
        P("password-reset", "anon", lambda d: reverse("password_reset")),
        P("password-reset-done", "anon", lambda d: reverse("password_reset_done")),
        P("password-reset-complete", "anon", lambda d: reverse("password_reset_complete")),
        P(
            "password-reset-confirm-invalid",
            "anon",
            lambda d: reverse("password_reset_confirm", args=["x", "bad"]),
        ),
        # characters. Alice has characters, so `mine` redirects for her.
        P("characters-mine-empty", "gm_only", _c("characters:mine")),
        P("characters-slips-print", "alice", _c("characters:slips_print")),
        P(
            "characters-slips-print-aria",
            "alice",
            lambda d: reverse("characters:slips_print", args=[d.slug]) + f"?characters={d.aria.pk}",
        ),
        P(
            "characters-print-item-choose",
            "alice",
            _c("characters:print_item", "aria.pk", "owned_item.pk"),
        ),
        P(
            "print-session-pack-modal",
            "alice",
            _c("accounts:player_dashboard"),
            action="print_session_pack_modal",
            modal_url=_c("accounts:print_session_pack_modal", "aria.pk"),
        ),
        P(
            "characters-print-item-full",
            "alice",
            lambda d: (
                reverse("characters:print_item", args=[d.slug, d.aria.pk, d.owned_item.pk])
                + "?layout=full"
            ),
        ),
        P(
            "characters-print-item-grid",
            "alice",
            lambda d: (
                reverse("characters:print_item", args=[d.slug, d.aria.pk, d.owned_item.pk])
                + "?layout=grid"
            ),
        ),
        P(
            "characters-print-items-per-item",
            "alice",
            lambda d: reverse("characters:print_items", args=[d.slug, d.aria.pk]) + "?copies=item",
        ),
        P(
            "characters-print-item-grid-per-item",
            "alice",
            lambda d: (
                reverse("characters:print_item", args=[d.slug, d.aria.pk, d.owned_item.pk])
                + "?layout=grid&copies=item"
            ),
        ),
        P("characters-junk", "alice", _c("characters:junk", "aria.pk", "torch.pk")),
        P(
            "characters-junk-modal",
            "alice",
            _c("characters:detail", "aria.pk"),
            action="junk_modal",
            modal_url=_c("characters:junk", "aria.pk", "torch.pk"),
        ),
        P("characters-note", "alice", _c("characters:note", "aria.pk", "torch.pk")),
        P(
            "characters-note-modal",
            "alice",
            _c("characters:detail", "aria.pk"),
            action="note_modal",
            modal_url=_c("characters:note", "aria.pk", "torch.pk"),
        ),
        P(
            "characters-consume-modal",
            "alice",
            _c("characters:detail", "aria.pk"),
            action="consume_modal",
            modal_url=_c("characters:player_consume", "aria.pk", "owned_item.pk"),
        ),
        # shops
        P("shops-stall-borin", "alice", _c("shops:player_shop", "borin.pk")),
        P("shops-stall-own", "bob", _c("shops:player_shop", "borin.pk")),
        P("shops-stall-buy", "alice", _c("shops:player_shop_buy", "borin.pk", "torch.pk")),
        P(
            "shops-stall-buy-modal",
            "alice",
            _c("shops:player_shop", "borin.pk"),
            action="stall_buy_modal",
            modal_url=_c("shops:player_shop_buy", "borin.pk", "torch.pk"),
        ),
        P("shops-sell-junk", "alice", _c("shops:sell_junk", "caravan.pk")),
        P(
            "shops-sell-junk-modal",
            "alice",
            _c("shops:detail", "caravan.pk"),
            action="sell_junk_modal",
            modal_url=_c("shops:sell_junk", "caravan.pk"),
        ),
        # The confirm modal comes from a POST, so there is no fragment URL to fetch.
        P("shops-sell-modal", "alice", _c("shops:detail", "caravan.pk"), action="sell_modal"),
        # items
        P("items-references", "gm", _c("items:references")),
        P(
            "items-where-to-buy-modal",
            "alice",
            _c("items:index"),
            action="where_to_buy_modal",
            modal_url=_c("items:where_to_buy", "item.pk"),
        ),
        P(
            "items-details-modal",
            "alice",
            _c("items:index"),
            action="details_modal",
            modal_url=_c("items:details_modal", "item.pk"),
        ),
        # downtime
        P("downtime-requests-alice", "alice", _c("downtime:requests")),
        P("downtime-requests-gm-only", "gm_only", _c("downtime:requests")),
        P("downtime-request-new", "alice", _c("downtime:request_new")),
        P("downtime-points-award", "gm_only", _c("downtime:points_award")),
        P("downtime-result", "alice", _c("downtime:result", "result.pk")),
        P("downtime-replay", "alice", _c("downtime:replay", "result.pk")),
        P("downtime-action-edit", "gm", _c("downtime:action_edit", "bakery.pk")),
        P("downtime-agenda-add", "gm", _c("downtime:agenda_add")),
        P("downtime-agenda-action-edit", "gm", _c("downtime:agenda_action_edit", "bakery.pk")),
        P(
            "downtime-agenda-add-modal",
            "gm",
            _c("downtime:agenda"),
            action="agenda_add_modal",
            # The "+" trigger is hidden at 390 px (the agenda is a list there).
            widths=(1280,),
            audit_widths=(1920, 1280, 768),
            modal_url=_c("downtime:agenda_add"),
        ),
        # play sessions
        P("play-sessions-detail", "gm", _c("play_sessions:session_detail", "play_session.pk")),
        P(
            "play-sessions-detail-player",
            "alice",
            _c("play_sessions:session_detail", "play_session.pk"),
        ),
        # map
        P(
            "map-visits",
            "gm",
            lambda d: reverse(
                "map:visits", args=[d.slug, d.map.pk, d.location.tile.q, d.location.tile.r]
            ),
        ),
        P("map-found", "gm", _c("map:found", "location.pk")),
        P(
            "map-credit",
            "gm",
            lambda d: reverse("map:credit", args=[d.slug, d.location.pk, "discovered"]),
        ),
        # inbox gives
        P("accounts-message-give-items", "gm", _c("accounts:message_give_items", "message.pk")),
        P("accounts-message-give-map", "gm", _c("accounts:message_give_map", "message.pk")),
        P(
            "accounts-message-status-confirm",
            "gm",
            lambda d: reverse(
                "accounts:message_status_confirm", args=[d.slug, d.message.pk, "handled"]
            ),
        ),
        P(
            "inbox-give-items-modal",
            "gm",
            _c("accounts:message_inbox"),
            action="give_items_modal",
            modal_url=_c("accounts:message_give_items", "message.pk"),
        ),
        P(
            "inbox-status-modal",
            "gm",
            _c("accounts:message_inbox"),
            action="status_modal",
            modal_url=lambda d: reverse(
                "accounts:message_status_confirm", args=[d.slug, d.message.pk, "handled"]
            ),
        ),
        # Quest turn-in is NOT a modal: it is an inline card with a POST form on the quest
        # detail page, so `quests-detail` already captures it.
    ]
    # Role variants. A page that a role cannot reach (403) is left out.
    for role, suffix in (("gm_only", "gm-only"), ("club_admin", "club-admin")):
        pages += [
            P(f"club-home-{suffix}", role, lambda d: reverse("club_home", args=[d.slug])),
            P(f"home-{suffix}", role, lambda d: reverse("home")),
            P(f"items-index-{suffix}", role, _c("items:index")),
            P(f"items-detail-{suffix}", role, _c("items:detail", "item.pk")),
            P(f"shops-index-{suffix}", role, _c("shops:index")),
            P(f"shops-detail-caravan-{suffix}", role, _c("shops:detail", "caravan.pk")),
            P(f"quests-index-{suffix}", role, _c("quests:index")),
            P(f"quests-detail-{suffix}", role, _c("quests:detail", "quest.pk")),
            P(f"downtime-play-{suffix}", role, lambda d: reverse("downtime:play", args=[d.slug])),
            P(f"map-index-{suffix}", role, _c("map:index")),
            P(f"map-detail-{suffix}", role, _c("map:detail", "map.pk")),
            P(f"ledger-index-{suffix}", role, _c("ledger:index")),
        ]
    # Player dashboard (only for players, not GMs/admins)
    for role in ("alice", "bob"):
        pages += [
            P(
                f"dashboard-{role}",
                role,
                lambda d: reverse("accounts:player_dashboard", args=[d.slug]),
            ),
        ]
    pages += [
        P("characters-index-gm-only", "gm_only", _c("characters:index")),
        P("characters-detail-gm-only", "gm_only", _c("characters:detail", "aria.pk")),
        P("agent-index-gm-only", "gm_only", _c("agent_access:index")),
        P("agent-batches-gm-only", "gm_only", _c("agent_access:batches")),
        P("accounts-index-club-admin", "club_admin", _c("accounts:index")),
        P(
            "people-roles-modal",
            "club_admin",
            _c("accounts:index"),
            action="roles_modal",
            modal_url=lambda d: reverse(
                "accounts:member_roles", args=[d.slug, d.alice_membership.pk]
            ),
        ),
        P("accounts-message-inbox-club-admin", "club_admin", _c("accounts:message_inbox")),
        P("shops-manage-list-club-admin", "club_admin", _c("shops:manage_list")),
        P("shops-street-editor", "club_admin", _c("shops:street_editor")),
        P("quests-manage-club-admin", "club_admin", _c("quests:manage")),
        P("downtime-agenda-club-admin", "club_admin", _c("downtime:agenda")),
    ]
    names = [p.name for p in pages]
    assert len(names) == len(set(names)), "duplicate page names"
    return pages


PAGES = _build_pages()
