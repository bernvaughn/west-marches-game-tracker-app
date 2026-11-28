import datetime

import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.demo import DEMO_LOGINS, DEMO_PASSWORD
from accounts.models import Club, Membership, Message, SiteFeedback, User, WhitelistEntry
from downtime.models import DowntimePointRequest
from items.models import ClubWeightSettings, ContainerSlot, ContainerSlotOption, Item
from items.opening import open_container
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import available_items, coin_balance
from mail.models import ClubMailSettings
from map.models import HexMap, Location, Tile, TileVisit, XPLevel
from play_sessions.models import (
    AttendanceHint,
    PlayerRSVP,
    PlaySession,
    SessionAttendance,
    SessionAward,
    SessionSettings,
)
from player_characters.models import (
    Character,
    CharacterStatusChange,
    ItemNote,
    JunkMark,
    SelectedCharacter,
)
from player_characters.sheet import xp_progress
from player_items.models import PlayerItem, PlayerItemChange, PlayerNotice
from quests.models import Quest, QuestRequirement, QuestReward
from shops.models import Rotation, Shop, ShopStock
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassLine,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)

pytestmark = [pytest.mark.story("FOUNDATION"), pytest.mark.django_db]

MODELS = [
    User,
    Club,
    Membership,
    Character,
    Item,
    Shop,
    ShopStock,
    Rotation,
    Quest,
    QuestRequirement,
    QuestReward,
    HexMap,
    Tile,
    Location,
    TileVisit,
    XPLevel,
    LedgerEntry,
    LedgerLine,
    ContainerSlot,
    ContainerSlotOption,
    StartingEquipmentClassLine,
    StartingEquipmentBackgroundLine,
    ItemNote,
    DowntimePointRequest,
    StartingEquipmentRequest,
    MagicItemStartingOption,
    SiteFeedback,
    WhitelistEntry,
    PlaySession,
    PlayerRSVP,
    SessionAttendance,
    SessionAward,
    SessionSettings,
    AttendanceHint,
    PlayerItem,
    PlayerItemChange,
    PlayerNotice,
    CharacterStatusChange,
    ClubWeightSettings,
    ClubMailSettings,
]


def counts():
    return [m.objects.count() for m in MODELS]


def test_seed_twice_is_idempotent(capsys):
    call_command("seed_demo")
    first = counts()
    assert all(first)
    call_command("seed_demo")
    assert counts() == first
    out = capsys.readouterr().out
    assert DEMO_PASSWORD in out
    for email, _ in DEMO_LOGINS:
        assert email in out


def test_balances_and_shops():
    call_command("seed_demo")
    assert coin_balance(Character.objects.get(name="Aria Windrunner")) == 5000
    assert coin_balance(Character.objects.get(name="Borin Stonefist")) == 2000
    today = datetime.date.today()
    rotations = Rotation.objects.all()
    assert rotations.filter(close_date__isnull=True, open_date__lte=today).exists()
    assert rotations.filter(close_date__gte=today, open_date__lte=today).exists()
    assert ShopStock.objects.filter(quantity__isnull=True).exists()
    assert ShopStock.objects.filter(quantity__isnull=False).exists()


@pytest.mark.parametrize("email", [e for e, _ in DEMO_LOGINS])
def test_demo_logins(client, email):
    call_command("seed_demo")
    assert client.login(username=email, password=DEMO_PASSWORD)
    # Follow redirect to dashboard for players
    response = client.get("/c/demo/", follow=True)
    assert response.status_code == 200


def test_demo_shop_silhouettes_idempotent():
    call_command("seed_demo")
    got = dict(Shop.objects.values_list("name", "silhouette"))
    assert got["The Rusty Lantern"] == "burly_innkeeper"
    assert got["Wandering Caravan"] == "veiled_merchant"
    assert got["General Store"] == "halfling_grocer"
    # A pre-U36 database. The General Store seeder never edits an existing shop,
    # so leave it out of the reset-and-restore check.
    Shop.objects.exclude(name="General Store").update(silhouette=Shop.Silhouette.HOODED_TRADER)
    call_command("seed_demo")
    assert dict(Shop.objects.values_list("name", "silhouette")) == got
    call_command("seed_demo")
    assert dict(Shop.objects.values_list("name", "silhouette")) == got


def test_seed_demo_creates_starting_equipment_template():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    template = StartingEquipmentTemplate.objects.get(club=club, name="2024 D&D Default")
    assert template.is_active
    assert template.class_entries.exists()
    assert template.background_entries.exists()
    assert template.level_coins.exists()


def test_seed_demo_twice_does_not_duplicate_template():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    template = StartingEquipmentTemplate.objects.get(club=club, name="2024 D&D Default")
    class_count = template.class_entries.count()
    background_count = template.background_entries.count()
    level_coins_count = template.level_coins.count()

    call_command("seed_demo")

    assert StartingEquipmentTemplate.objects.filter(club=club, name="2024 D&D Default").count() == 1
    template.refresh_from_db()
    assert template.class_entries.count() == class_count
    assert template.background_entries.count() == background_count
    assert template.level_coins.count() == level_coins_count


def test_demo_character_shows_claim_button_for_owner(client):
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    alice = User.objects.get(email="alice@example.com")
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    assert aria.char_class
    assert not aria.starting_equipment_claimed

    client.force_login(alice)
    response = client.get(
        reverse(
            "characters:detail",
            kwargs={"club_slug": club.slug, "pk": aria.pk},
        )
    )
    assert response.status_code == 200
    assert response.context["can_claim_starting_equipment"] is True


def test_seed_demo_packs_are_openable_containers():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    for name in ("Explorer's Pack", "Priest's Pack", "Dungeoneer's Pack"):
        pack = Item.objects.get(club=club, name=name)
        assert pack.is_container, name
        assert pack.slots.exists(), name
    assert StartingEquipmentClassLine.objects.filter(
        class_entry__template__club=club, is_choice=True
    ).exists()


def test_tilda_has_unopened_priests_pack_that_opens():
    call_command("seed_demo")
    call_command("seed_demo")  # the gear note guard keeps it to one pack
    club = Club.objects.get(slug="demo")
    tilda = Character.objects.get(club=club, name="Tilda Brightwater")
    assert tilda.owner.user.email == "bob@example.com"
    assert not tilda.starting_equipment_claimed
    pack = Item.objects.get(club=club, name="Priest's Pack")
    assert available_items(tilda).get(pack.pk) == 1
    assert not LedgerEntry.objects.filter(character=tilda, kind=LedgerEntry.Kind.OPENED).exists()

    opening = open_container(tilda, pack, tilda.owner.user)
    assert opening.result
    held = available_items(tilda)
    assert held.get(pack.pk, 0) == 0
    assert held[Item.objects.get(club=club, name="Censer").pk] == 1


def test_stacked_items_exist():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    parchment = Item.objects.get(club=club, name="Parchment")
    cord = Item.objects.get(club=club, name="Hempen cord")
    assert parchment.is_stacked
    assert parchment.unit_name == "sheet"
    assert parchment.value_units == 10
    assert cord.is_stacked
    assert cord.unit_name == "ft"
    assert cord.value_units == 50


def test_bundle_stock_rows_exist():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    lantern = Shop.objects.get(club=club, name="The Rusty Lantern")
    parchment = Item.objects.get(club=club, name="Parchment")
    cord = Item.objects.get(club=club, name="Hempen cord")
    # Parchment bundle of 10 (unlimited)
    stock = ShopStock.objects.get(shop=lantern, item=parchment, bundle_units=10)
    assert stock.quantity is None
    # Hempen cord bundle of 50 (qty 4)
    stock = ShopStock.objects.get(shop=lantern, item=cord, bundle_units=50)
    assert stock.quantity == 4


def test_aria_holds_stacked_units():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    parchment = Item.objects.get(club=club, name="Parchment")
    cord = Item.objects.get(club=club, name="Hempen cord")
    held = available_items(aria)
    assert held[parchment.pk] == 25
    assert held[cord.pk] == 40


def test_parchment_junk_mark_exists():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    parchment = Item.objects.get(club=club, name="Parchment")
    junk = JunkMark.objects.get(character=aria, item=parchment)
    assert junk.quantity == 5


def test_item_note_exists():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    rope = Item.objects.get(club=club, name="Rope")
    note = ItemNote.objects.get(character=aria, item=rope)
    assert "climbing" in note.text.lower()


def test_cartographer_quest_has_unit_requirement():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    quest = Quest.objects.get(club=club, name="Maps for the Cartographer")
    parchment = Item.objects.get(club=club, name="Parchment")
    req = QuestRequirement.objects.get(quest=quest, item=parchment)
    assert req.quantity == 10


def test_pending_point_request_exists():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    bob = Membership.objects.get(club=club, user__email="bob@example.com")
    req = DowntimePointRequest.objects.get(club=club, requested_by=bob, status="pending")
    assert req.points == 1
    assert "bakery" in req.note.lower()
    assert req.characters.filter(name="Borin Stonefist").exists()


def test_magic_option_exists():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    template = StartingEquipmentTemplate.objects.get(club=club, name="2024 D&D Default")
    moonstone = Item.objects.get(club=club, name="Moonstone amulet")
    opt = MagicItemStartingOption.objects.get(template=template, item=moonstone)
    assert opt.max_per_character == 1


def test_pending_starting_request_exists():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    tilda = Character.objects.get(club=club, name="Tilda Brightwater")
    req = StartingEquipmentRequest.objects.get(club=club, character=tilda, status="pending")
    assert req.quantity == 1
    # Linked message exists
    assert req.message is not None
    assert req.message.kind == Message.Kind.STARTING_REQUEST
    # Sent by the requesting player, as request_new does
    assert req.message.sender == tilda.owner


def test_site_feedback_exists():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    alice = User.objects.get(email="alice@example.com")
    fb = SiteFeedback.objects.get(user=alice, club=club, kind="bug")
    assert "tooltip" in fb.body.lower()
    assert fb.page_url == "/c/demo/"
    assert fb.status == "open"


def test_whitelist_entry_exists():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    entry = WhitelistEntry.objects.get(club=club, email="newplayer@example.com")
    assert entry.email == "newplayer@example.com"


def test_wren_is_level_up_ready():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    wren = Character.objects.get(club=club, name="Wren Thistledown")
    assert wren.level == 2
    progress = xp_progress(wren)
    assert progress["xp_level"] == 3
    assert progress["level_up_ready"] is True


def test_borin_holds_one_wolf_pelt():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    borin = Character.objects.get(club=club, name="Borin Stonefist")
    pelt = Item.objects.get(club=club, name="Wolf pelt")
    assert available_items(borin)[pelt.pk] == 1


def test_borin_quest_board_shows_one_of_three(client):
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    bob = User.objects.get(email="bob@example.com")
    borin = Character.objects.get(club=club, name="Borin Stonefist")
    membership = Membership.objects.get(user=bob, club=club)
    SelectedCharacter.objects.update_or_create(membership=membership, defaults={"character": borin})
    client.force_login(bob)
    response = client.get(reverse("quests:index", args=["demo"]))
    assert response.status_code == 200
    assert "1 of 3" in response.content.decode()


def test_second_seed_demo_adds_no_spare_pelt():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    borin = Character.objects.get(club=club, name="Borin Stonefist")
    assert LedgerEntry.objects.filter(character=borin, note="Demo: a spare pelt").count() == 1
    call_command("seed_demo")
    assert LedgerEntry.objects.filter(character=borin, note="Demo: a spare pelt").count() == 1


def test_bundle_buy_smoke():
    """Smoke test: buy a bundle through shops.buying.buy."""
    from shops.buying import buy

    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    parchment = Item.objects.get(club=club, name="Parchment")
    lantern = Shop.objects.get(club=club, name="The Rusty Lantern")

    # Parchment bundle of 10 is unlimited; buy one bundle (10 sheets)
    stock = ShopStock.objects.get(shop=lantern, item=parchment, bundle_units=10)
    buy(aria, stock, quantity=1)  # raises on failure
    # Aria now has 35 sheets (25 + 10)
    from ledger.services import available_items

    assert available_items(aria)[parchment.pk] == 35


def test_demo_sessions_exist():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    assert PlaySession.objects.filter(club=club, title="The Goblin Caves").exists()
    assert PlaySession.objects.filter(club=club, title="Ruins of Karth").exists()
    assert PlaySession.objects.filter(club=club, title="The Sunless Cellar").exists()
    assert PlaySession.objects.filter(club=club, title="The Whispering Caves").exists()


def test_demo_session_settings_and_token():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    settings = SessionSettings.objects.get(club=club)
    assert settings.award_points == 1
    assert settings.feed_token != ""


def test_demo_rsvps_exist():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    alice = Membership.objects.get(club=club, user__email="alice@example.com")
    bob = Membership.objects.get(club=club, user__email="bob@example.com")
    session = PlaySession.objects.get(club=club, title="The Sunless Cellar")
    alice_rsvp = PlayerRSVP.objects.get(session=session, member=alice)
    bob_rsvp = PlayerRSVP.objects.get(session=session, member=bob)
    assert alice_rsvp.answer == "yes"
    assert bob_rsvp.answer == "maybe"


def test_demo_attendance_and_awards():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    session = PlaySession.objects.get(club=club, title="The Goblin Caves")
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    borin = Character.objects.get(club=club, name="Borin Stonefist")
    assert SessionAttendance.objects.filter(session=session, character=aria).exists()
    assert SessionAttendance.objects.filter(session=session, character=borin).exists()
    assert SessionAward.objects.filter(session=session, character=aria).exists()
    assert SessionAward.objects.filter(session=session, character=borin).exists()


def test_demo_attendance_hint():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    session = PlaySession.objects.get(club=club, title="The Sunless Cellar")
    wren = Character.objects.get(club=club, name="Wren Thistledown")
    assert AttendanceHint.objects.filter(session=session, character=wren).exists()


def test_demo_weighted_items():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    for name in (
        "Rope",
        "Torch",
        "Longsword",
        "Healing potion",
        "Wolf pelt",
        "Moonstone amulet",
        "Parchment",
        "Hempen cord",
    ):
        item = Item.objects.get(club=club, name=name)
        assert item.weight_hundredth_lb is not None, f"{name} has no weight"


def test_demo_club_weight_settings():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    settings = ClubWeightSettings.objects.get(club=club)
    assert settings.count_coin_weight is True


def test_demo_borin_capacity_override():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    borin = Character.objects.get(club=club, name="Borin Stonefist")
    assert borin.carrying_capacity_lb == 300


def test_demo_dead_and_archived_characters():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    garrick = Character.objects.get(club=club, name="Garrick Ashdown")
    pip = Character.objects.get(club=club, name="Pip Quickfoot")
    assert garrick.is_dead
    assert garrick.died_on is not None
    assert pip.is_archived
    assert pip.archived_at is not None


def test_demo_player_items():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    wren = Character.objects.get(club=club, name="Wren Thistledown")
    borin = Character.objects.get(club=club, name="Borin Stonefist")
    assert PlayerItem.objects.filter(character=aria, name="Grandmother's locket").exists()
    assert PlayerItem.objects.filter(character=wren, name="Lockpicks").exists()
    # Borin has two lockpicks (same name_key as Wren's, grouped for merge)
    assert PlayerItem.objects.filter(character=borin, name="lockpicks").exists()
    assert PlayerItem.objects.filter(character=borin, name="Whetstone").exists()


def test_demo_player_notice():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    alice = Membership.objects.get(club=club, user__email="alice@example.com")
    assert PlayerNotice.objects.filter(membership=alice, kind="item_promoted").exists()


def test_demo_club_mail_settings():
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    settings = ClubMailSettings.objects.get(club=club)
    assert settings.contact_email == "gm@example.com"


def test_second_seed_demo_adds_no_session_rows():
    """A second run adds no SessionAward, PlayerItemChange, CharacterStatusChange or point rows."""
    call_command("seed_demo")
    club = Club.objects.get(slug="demo")
    session = PlaySession.objects.get(club=club, title="The Goblin Caves")
    aria = Character.objects.get(club=club, name="Aria Windrunner")

    award_count = SessionAward.objects.filter(session=session, character=aria).count()
    change_count = PlayerItemChange.objects.filter(club=club).count()
    status_count = CharacterStatusChange.objects.filter(character__club=club).count()

    call_command("seed_demo")

    assert SessionAward.objects.filter(session=session, character=aria).count() == award_count
    assert PlayerItemChange.objects.filter(club=club).count() == change_count
    assert CharacterStatusChange.objects.filter(character__club=club).count() == status_count
    # No duplicate attendance rows
    assert SessionAttendance.objects.filter(session=session, character=aria).count() == 1
