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
}
BOTH = (1280, 390)
MODAL_ACTIONS = {"buy_modal", "tile_modal", "grant_modal"}


@dataclass(frozen=True)
class Page:
    name: str
    role: str
    url: Callable[[SimpleNamespace], str]
    action: str | None = None
    widths: tuple[int, ...] = BOTH
    # For modal actions: the fragment URL that the smoke test fetches with HX-Request.
    modal_url: Callable[[SimpleNamespace], str] | None = None


def extra_fixtures():
    """Add objects that `seed_demo` lacks. Safe to run twice."""
    from player_characters.models import Character, Trade
    from player_characters.trade_services import propose_trade

    if Trade.objects.exists():
        return
    from ledger.services import Line

    aria = Character.objects.get(name="Aria Windrunner")
    borin = Character.objects.get(name="Borin Stonefist")
    propose_trade(aria, borin, [Line(coins=100)], "Swap for the pelts?", aria.owner.user)


def demo_objects() -> SimpleNamespace:
    from accounts.models import Club, Membership, Message
    from agent_access.models import ProposedBatch, ProposedItem
    from items.models import Item
    from map.models import Encounter, HexMap, Location, MapRequest
    from player_characters.models import Character, Trade
    from quests.models import Quest
    from shops.models import Rotation, Shop, ShopStock

    club = Club.objects.get(slug="demo")
    batch = ProposedBatch.objects.get(idempotency_key="demo-session-1")
    wolf_den = Location.objects.get(name="Wolf Den")
    caravan = Shop.objects.get(name="Wandering Caravan")
    return SimpleNamespace(
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
        message=Message.objects.first(),
        alice_membership=Membership.objects.get(user__email="alice@example.com", club=club),
        map_request=MapRequest.objects.first(),
        item=Item.objects.filter(club=club).order_by("name").first(),
        trade=Trade.objects.first(),
    )


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
        ),
        # accounts
        P("accounts-index", "gm", _c("accounts:index")),
        P("accounts-whitelist", "gm", _c("accounts:whitelist")),
        P("accounts-reset-password", "gm", _c("accounts:reset_password", "alice_membership.pk")),
        P("accounts-message-new", "alice", _c("accounts:message_new")),
        P("accounts-message-inbox", "gm", _c("accounts:message_inbox")),
        P("accounts-message-grant", "gm", _c("accounts:message_grant", "message.pk")),
        P(
            "inbox-grant-modal",
            "gm",
            _c("accounts:message_inbox"),
            action="grant_modal",
            modal_url=_c("accounts:message_grant", "message.pk"),
        ),
        # site admin
        P("site-clubs", "site_admin", lambda d: reverse("site_clubs")),
        P("site-club-new", "site_admin", lambda d: reverse("site_club_new")),
        P("site-settings", "site_admin", lambda d: reverse("site_settings")),
        # characters
        P("characters-index-alice", "alice", _c("characters:index")),
        P("characters-index-gm", "gm", _c("characters:index")),
        P("characters-create", "alice", _c("characters:create")),
        P("characters-detail-alice", "alice", _c("characters:detail", "aria.pk")),
        P("characters-detail-gm", "gm", _c("characters:detail", "aria.pk")),
        P("characters-edit", "alice", _c("characters:edit", "aria.pk")),
        P("characters-handover", "gm", _c("characters:handover", "aria.pk")),
        P("characters-adjust", "gm", _c("characters:adjust", "aria.pk")),
        P("characters-consume", "gm", _c("characters:consume", "aria.pk")),
        P("characters-transfer", "alice", _c("characters:transfer", "aria.pk")),
        P("characters-print-items", "alice", _c("characters:print_items", "aria.pk")),
        # trades
        P("trades-index", "alice", _c("trades:index")),
        P("trades-propose", "alice", _c("trades:propose")),
        P("trades-detail-alice", "alice", _c("trades:detail", "trade.pk")),
        P("trades-detail-bob", "bob", _c("trades:detail", "trade.pk")),
        # items
        P("items-index", "alice", _c("items:index")),
        P("items-index-gm", "gm", _c("items:index")),
        P("items-create", "gm", _c("items:create")),
        P("items-detail", "alice", _c("items:detail", "item.pk")),
        P("items-edit", "gm", _c("items:edit", "item.pk")),
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
        P("shops-sell", "alice", _c("shops:sell", "caravan.pk")),
        P("shops-manage-list", "gm", _c("shops:manage_list")),
        P("shops-manage-create", "gm", _c("shops:manage_create")),
        P("shops-manage-edit", "gm", _c("shops:manage_edit", "caravan.pk")),
        P("shops-stock-add", "gm", _c("shops:stock_add", "caravan.pk")),
        P("shops-stock-edit", "gm", _c("shops:stock_edit", "caravan.pk", "stock.pk")),
        P("shops-rotation-list", "gm", _c("shops:rotation_list")),
        P("shops-rotation-create", "gm", _c("shops:rotation_create")),
        P("shops-rotation-edit", "gm", _c("shops:rotation_edit", "rotation.pk")),
        # ledger
        P("ledger-index", "gm", _c("ledger:index")),
        P("ledger-character-history", "alice", _c("ledger:character_history", "aria.pk")),
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
    ]
    names = [p.name for p in pages]
    assert len(names) == len(set(names)), "duplicate page names"
    return pages


PAGES = _build_pages()
