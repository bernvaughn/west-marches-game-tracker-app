"""Tests for new-club seeding via accounts.club_seeding.seed_new_club."""

import pytest
from django.db import transaction
from django.db.models import Count
from django.urls import reverse

from accounts.club_seeding import seed_new_club
from accounts.models import Club, Membership, SiteFeedback, User
from character_options.defaults import DEFAULT_CLASSES
from character_options.models import Background, CharacterClass, Species
from downtime.models import DowntimeAction, DowntimePointRequest
from items.models import Item
from map.models import HexMap, XPLevel
from map.xp import DEFAULT_XP_TABLE
from player_characters.models import Character, ItemNote
from quests.models import Quest
from shops.models import Shop
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)
from starting_equipment.seeding import DEFAULT_TEMPLATE_NAME, StartingEquipmentSeedError

pytestmark = pytest.mark.django_db

NEW = "site_club_new"


def _post(client, **over):
    data = {
        "name": "Club C",
        "slug": "",
        "admin_email": "Boss@Example.com",
        "admin_display_name": "Boss",
        "timezone": "UTC",
    }
    data.update(over)
    return client.post(reverse(NEW), data)


def test_view_seeds_club(site_admin, login):
    c = login(site_admin)
    r = _post(c)
    assert r.status_code == 200
    club = Club.objects.get(slug="club-c")

    assert Item.objects.filter(club=club).count() > 0

    template = StartingEquipmentTemplate.objects.get(club=club, name=DEFAULT_TEMPLATE_NAME)
    assert template.is_active

    class_names = {
        entry.class_option.name
        for entry in StartingEquipmentClassEntry.objects.filter(template=template)
    }
    assert class_names == set(DEFAULT_CLASSES)

    assert XPLevel.objects.filter(club=club).count() == len(DEFAULT_XP_TABLE)

    assert Species.objects.filter(club=club).exists()
    assert CharacterClass.objects.filter(club=club).exists()
    assert Background.objects.filter(club=club).exists()

    memberships = Membership.objects.filter(club=club)
    assert memberships.count() == 1
    assert memberships.get().is_club_admin

    assert Character.objects.filter(club=club).count() == 0
    assert Shop.objects.filter(club=club).count() == 1
    assert Quest.objects.filter(club=club).count() == 0
    assert HexMap.objects.filter(club=club).count() == 0
    assert DowntimeAction.objects.filter(club=club).count() == 0


def test_seed_failure_rolls_back_club_creation(site_admin, login, monkeypatch):
    def boom(club, **kwargs):
        raise StartingEquipmentSeedError("starting equipment failed")

    monkeypatch.setattr("accounts.club_seeding.seed_default_starting_equipment", boom)
    c = login(site_admin)
    with pytest.raises(StartingEquipmentSeedError):
        _post(c)

    assert not Club.objects.filter(slug="club-c").exists()
    assert not User.objects.filter(email="boss@example.com").exists()
    assert not Membership.objects.filter(user__email="boss@example.com").exists()


def test_general_store_failure_rolls_back_club_via_view(site_admin, login, monkeypatch):
    """A failure in the last seeder (General Store) leaves no Club row after a view post."""

    def boom(club, **kwargs):
        raise StartingEquipmentSeedError("general store failed")

    monkeypatch.setattr("accounts.club_seeding.seed_default_general_store", boom)
    c = login(site_admin)
    with pytest.raises(StartingEquipmentSeedError):
        _post(c)

    assert not Club.objects.filter(slug="club-c").exists()
    assert not Item.objects.filter(club__slug="club-c").exists()
    assert not Membership.objects.filter(user__email="boss@example.com").exists()


def test_seed_failure_rolls_back_xp_and_options(club, monkeypatch):
    def boom(club, **kwargs):
        raise StartingEquipmentSeedError("starting equipment failed")

    monkeypatch.setattr("accounts.club_seeding.seed_default_starting_equipment", boom)

    # The club's post_save signal seeds the XP table on creation;
    # species/classes/backgrounds and items are not seeded yet.
    assert XPLevel.objects.filter(club=club).count() == len(DEFAULT_XP_TABLE)
    assert Species.objects.filter(club=club).count() == 0
    assert CharacterClass.objects.filter(club=club).count() == 0
    assert Background.objects.filter(club=club).count() == 0
    assert Item.objects.filter(club=club).count() == 0

    with pytest.raises(StartingEquipmentSeedError):
        with transaction.atomic():
            seed_new_club(club)

    # Rows created inside the failed block are rolled back with the club.
    assert Species.objects.filter(club=club).count() == 0
    assert CharacterClass.objects.filter(club=club).count() == 0
    assert Background.objects.filter(club=club).count() == 0
    assert Item.objects.filter(club=club).count() == 0


def test_items_isolated_per_club(club, other_club):
    seed_new_club(club)
    seed_new_club(other_club)

    a_items = Item.objects.filter(club=club)
    b_items = Item.objects.filter(club=other_club)
    assert a_items.count() == b_items.count()
    assert a_items.count() > 0
    assert set(a_items.values_list("id", flat=True)).isdisjoint(
        set(b_items.values_list("id", flat=True))
    )

    # Editing an item in club A leaves club B unchanged.
    item_a = a_items.get(name="Greataxe")
    item_a.value_cp = 1
    item_a.save(update_fields=["value_cp"])
    assert Item.objects.filter(club=other_club, name="Greataxe").get().value_cp != 1

    # Every template entry's items belong to its own club.
    for seeded_club in (club, other_club):
        template = StartingEquipmentTemplate.objects.get(
            club=seeded_club, name=DEFAULT_TEMPLATE_NAME
        )
        for entry in template.class_entries.all():
            for line in entry.lines.all():
                assert line.item.club_id == seeded_club.id
        for entry in template.background_entries.all():
            for line in entry.lines.all():
                assert line.item.club_id == seeded_club.id


def test_seed_new_club_is_idempotent(club):
    seed_new_club(club)
    item_count = Item.objects.filter(club=club).count()
    template = StartingEquipmentTemplate.objects.get(club=club, name=DEFAULT_TEMPLATE_NAME)
    entry_count = StartingEquipmentClassEntry.objects.filter(template=template).count()

    result = seed_new_club(club)

    assert Item.objects.filter(club=club).count() == item_count
    assert StartingEquipmentClassEntry.objects.filter(template=template).count() == entry_count
    assert result["starting_equipment"].skipped is True


def test_seed_new_club_return_value(club):
    result = seed_new_club(club)
    assert set(result) == {"options", "starting_equipment", "general_store"}
    assert result["starting_equipment"].template_created is True
    assert result["general_store"].shop_created is True


def test_seed_new_club_item_count_matches_docs(club):
    """README.md and docs/DATA_MODEL.md say "about 175 items". Update them if this fails."""
    seed_new_club(club)
    assert 165 <= Item.objects.filter(club=club).count() <= 185


def test_new_club_has_choice_groups():
    """New club's template has choice groups (is_choice=True lines) for classes and backgrounds."""
    club = Club.objects.create(name="Test Club", slug="test-club")
    seed_new_club(club)
    template = StartingEquipmentTemplate.objects.get(club=club, name=DEFAULT_TEMPLATE_NAME)

    # Class choice groups exist
    class_choice_lines = StartingEquipmentClassLine.objects.filter(
        class_entry__template=template, is_choice=True
    )
    assert class_choice_lines.exists()
    # Choice group slugs should be present
    class_choice_slugs = set(class_choice_lines.values_list("choice_group", flat=True))
    expected_class_groups = {
        "weapon",
        "simple_weapon",
        "melee_weapon",
        "armor",
        "ranged",
        "weapons",
        "pack",
        "focus",
        "instrument",
        "shield_or_weapon",
        "melee",
    }
    assert class_choice_slugs == expected_class_groups

    # Background choice groups exist (Artisan tools, Entertainer instrument, Soldier gaming_set)
    bg_choice_lines = StartingEquipmentBackgroundLine.objects.filter(
        background_entry__template=template, is_choice=True
    )
    assert bg_choice_lines.exists()
    bg_choice_slugs = set(bg_choice_lines.values_list("choice_group", flat=True))
    assert bg_choice_slugs == {"tools", "instrument", "gaming_set"}


def test_new_club_has_openable_packs():
    """New club's packs are containers with slots."""
    club = Club.objects.create(name="Test Club", slug="test-club")
    seed_new_club(club)

    pack_names = (
        "Explorer's Pack",
        "Priest's Pack",
        "Dungeoneer's Pack",
        "Burglar's Pack",
        "Scholar's Pack",
        "Diplomat's Pack",
        "Entertainer's Pack",
    )
    for name in pack_names:
        pack = Item.objects.get(club=club, name=name)
        assert pack.is_container, name
        assert pack.slots.exists(), name


def test_new_club_has_general_store_with_stock():
    """New club gets the General Store with stock."""
    club = Club.objects.create(name="Test Club", slug="test-club")
    seed_new_club(club)

    store = Shop.objects.get(club=club, name="General Store")
    assert store.keeper_name == "Mabel Packwell"
    assert store.building == Shop.Building.GENERAL_STORE
    assert store.street_position == 0
    assert store.stock.count() > 0


def test_seed_new_club_twice_unchanged_counts(club):
    """Seeding twice leaves shop, stock and pack-slot counts unchanged."""
    seed_new_club(club)

    shop_count = Shop.objects.filter(club=club).count()
    stock_count = Shop.objects.filter(club=club).first().stock.count() if shop_count else 0
    # Count pack slots by summing slot counts per container
    pack_slot_count = sum(
        Item.objects.filter(club=club, is_container=True)
        .annotate(slot_count=Count("slots"))
        .values_list("slot_count", flat=True)
    )

    seed_new_club(club)

    assert Shop.objects.filter(club=club).count() == shop_count
    assert Shop.objects.filter(club=club).first().stock.count() == stock_count
    # Pack slots should not be duplicated
    new_pack_slot_count = sum(
        Item.objects.filter(club=club, is_container=True)
        .annotate(slot_count=Count("slots"))
        .values_list("slot_count", flat=True)
    )
    assert new_pack_slot_count == pack_slot_count


def test_new_club_weights_twice_unchanged(club):
    """Seeding a new club twice leaves item weights unchanged."""
    seed_new_club(club)
    first_weights = {
        item.name: item.weight_hundredth_lb
        for item in Item.objects.filter(club=club).exclude(weight_hundredth_lb__isnull=True)
    }

    seed_new_club(club)

    second_weights = {
        item.name: item.weight_hundredth_lb
        for item in Item.objects.filter(club=club).exclude(weight_hundredth_lb__isnull=True)
    }
    assert first_weights == second_weights


def test_seed_failure_rolls_back_via_direct_call(club, monkeypatch):
    """A seeding failure inside seed_new_club rolls back the whole club (direct call)."""

    def boom(club, **kwargs):
        raise StartingEquipmentSeedError("boom")

    monkeypatch.setattr("accounts.club_seeding.seed_default_starting_equipment", boom)

    # XP table already seeded by post_save
    assert XPLevel.objects.filter(club=club).count() == len(DEFAULT_XP_TABLE)

    with pytest.raises(StartingEquipmentSeedError):
        with transaction.atomic():
            seed_new_club(club)

    # All rolled back
    assert Species.objects.filter(club=club).count() == 0
    assert CharacterClass.objects.filter(club=club).count() == 0
    assert Background.objects.filter(club=club).count() == 0
    assert Item.objects.filter(club=club).count() == 0


def test_demo_new_club_parity():
    """Demo club and a new club have the same pack names, choice-group
    slugs, General Store stock names, and weighted items."""
    from django.core.management import call_command

    # Seed demo club
    call_command("seed_demo")
    demo_club = Club.objects.get(slug="demo")

    # Create and seed a fresh club
    new_club = Club.objects.create(name="Parity Club", slug="parity-club")
    seed_new_club(new_club)

    # Pack names
    demo_packs = set(
        Item.objects.filter(club=demo_club, is_container=True).values_list("name", flat=True)
    )
    new_packs = set(
        Item.objects.filter(club=new_club, is_container=True).values_list("name", flat=True)
    )
    assert demo_packs == new_packs

    # Choice group slugs (class + background)
    demo_class_groups = set(
        StartingEquipmentClassLine.objects.filter(
            class_entry__template__club=demo_club, is_choice=True
        ).values_list("choice_group", flat=True)
    )
    new_class_groups = set(
        StartingEquipmentClassLine.objects.filter(
            class_entry__template__club=new_club, is_choice=True
        ).values_list("choice_group", flat=True)
    )
    assert demo_class_groups == new_class_groups

    demo_bg_groups = set(
        StartingEquipmentBackgroundLine.objects.filter(
            background_entry__template__club=demo_club, is_choice=True
        ).values_list("choice_group", flat=True)
    )
    new_bg_groups = set(
        StartingEquipmentBackgroundLine.objects.filter(
            background_entry__template__club=new_club, is_choice=True
        ).values_list("choice_group", flat=True)
    )
    assert demo_bg_groups == new_bg_groups

    # General Store stock names
    demo_store = Shop.objects.get(club=demo_club, name="General Store")
    new_store = Shop.objects.get(club=new_club, name="General Store")
    demo_stock = set(demo_store.stock.values_list("item__name", flat=True))
    new_stock = set(new_store.stock.values_list("item__name", flat=True))
    assert demo_stock == new_stock

    # Weighted items: every weighted item on the new club has the same weight on the demo club.
    demo_weights = {
        item.name: item.weight_hundredth_lb
        for item in Item.objects.filter(club=demo_club).exclude(weight_hundredth_lb__isnull=True)
    }
    new_weights = {
        item.name: item.weight_hundredth_lb
        for item in Item.objects.filter(club=new_club).exclude(weight_hundredth_lb__isnull=True)
    }
    for name, weight in new_weights.items():
        assert name in demo_weights, f"{name} weighted on new club but not on demo club"
        assert demo_weights[name] == weight, f"{name} weight differs: demo={demo_weights[name]} new={weight}"


def test_demo_weighted_items_are_not_on_new_club():
    """Demo-only weighted items (Healing potion, Wolf pelt, Moonstone amulet, etc.)
    are not on a new club - they are demo data only."""
    from django.core.management import call_command

    call_command("seed_demo")
    demo_club = Club.objects.get(slug="demo")

    new_club = Club.objects.create(name="Parity Club", slug="parity-club-4")
    seed_new_club(new_club)

    demo_weighted = set(
        Item.objects.filter(club=demo_club).exclude(weight_hundredth_lb__isnull=True).values_list("name", flat=True)
    )
    new_weighted = set(
        Item.objects.filter(club=new_club).exclude(weight_hundredth_lb__isnull=True).values_list("name", flat=True)
    )
    # Demo-only weighted items should NOT appear on a new club
    demo_only = {"Healing potion", "Wolf pelt", "Moonstone amulet", "Parchment", "Hempen cord"}
    assert demo_only.isdisjoint(new_weighted), f"Demo-only weights leaked to new club: {demo_only & new_weighted}"


def test_demo_stacked_is_new_club_stacked_plus_demo_extras():
    """Demo stacked gear is the new club's stacked gear plus Parchment and Hempen cord."""
    from django.core.management import call_command

    call_command("seed_demo")
    demo_club = Club.objects.get(slug="demo")

    new_club = Club.objects.create(name="Parity Club", slug="parity-club-3")
    seed_new_club(new_club)

    demo_stacked = {
        item.name for item in Item.objects.filter(club=demo_club, is_stacked=True).order_by("name")
    }
    new_stacked = {
        item.name for item in Item.objects.filter(club=new_club, is_stacked=True).order_by("name")
    }
    # Everything a new club gets stacked, the demo club also gets stacked.
    assert new_stacked <= demo_stacked
    # The demo club's only extra stacked items are its two demo-only supplies.
    assert demo_stacked - new_stacked == {"Parchment", "Hempen cord"}


def test_new_club_bundle_stock_matches_value_units():
    """Each stacked item on the new club's General Store sells in its unit-size bundle."""
    club = Club.objects.create(name="Bundle Club", slug="bundle-club")
    seed_new_club(club)

    store = Shop.objects.get(club=club, name="General Store")
    for stock in store.stock.select_related("item").filter(item__is_stacked=True):
        assert stock.bundle_units == stock.item.value_units, stock.item.name


def test_seed_new_club_twice_adds_no_stacked_items_or_stock():
    """Seeding a new club twice adds no stacked items and no stock rows."""
    club = Club.objects.create(name="Twice Club", slug="twice-club")
    seed_new_club(club)

    first_stacked = Item.objects.filter(club=club, is_stacked=True).count()
    store = Shop.objects.get(club=club, name="General Store")
    first_stock = store.stock.count()

    seed_new_club(club)

    assert Item.objects.filter(club=club, is_stacked=True).count() == first_stacked
    assert store.stock.count() == first_stock


def test_new_club_has_no_demo_only_rows():
    """A new club must not have demo-only rows (ItemNote, requests, feedback,
    sessions, player items, dead/archived characters, mail settings).
    Stacked ammunition items are now part of standard seeding."""
    new_club = Club.objects.create(name="Parity Club", slug="parity-club-2")
    seed_new_club(new_club)

    # Stacked ammunition items ARE expected (Arrows, Crossbow Bolts, etc.)
    stacked = Item.objects.filter(club=new_club, is_stacked=True)
    stacked_names = {item.name for item in stacked}
    expected_stacked = {
        "Arrows",
        "Crossbow Bolts",
        "Firearm Bullets",
        "Sling Bullets",
        "Needles",
        "Caltrops",
        "Ball Bearings",
        "Spikes, Iron",
    }
    assert stacked_names == expected_stacked

    # No ItemNote
    assert not ItemNote.objects.filter(character__club=new_club).exists()

    # No DowntimePointRequest
    assert not DowntimePointRequest.objects.filter(club=new_club).exists()

    # No StartingEquipmentRequest
    assert not StartingEquipmentRequest.objects.filter(club=new_club).exists()

    # No SiteFeedback
    assert not SiteFeedback.objects.filter(club=new_club).exists()

    # No MagicItemStartingOption (only created in demo)
    assert not MagicItemStartingOption.objects.filter(template__club=new_club).exists()

    # No sessions
    from play_sessions.models import PlaySession

    assert not PlaySession.objects.filter(club=new_club).exists()

    # No player items
    from player_items.models import PlayerItem

    assert not PlayerItem.objects.filter(club=new_club).exists()

    # No dead or archived characters
    from player_characters.models import Character

    assert not Character.objects.filter(club=new_club, died_on__isnull=False).exists()
    assert not Character.objects.filter(club=new_club, archived_at__isnull=False).exists()

    # No club mail settings
    from mail.models import ClubMailSettings

    assert not ClubMailSettings.objects.filter(club=new_club).exists()
