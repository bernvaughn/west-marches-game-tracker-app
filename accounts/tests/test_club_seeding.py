"""Tests for new-club seeding via accounts.club_seeding.seed_new_club."""

import pytest
from django.db import transaction
from django.urls import reverse

from accounts.club_seeding import seed_new_club
from accounts.models import Club, Membership, User
from character_options.defaults import DEFAULT_CLASSES
from character_options.models import Background, CharacterClass, Species
from downtime.models import DowntimeAction
from items.models import Item
from map.models import HexMap, XPLevel
from map.xp import DEFAULT_XP_TABLE
from player_characters.models import Character
from quests.models import Quest
from shops.models import Shop
from starting_equipment.models import (
    StartingEquipmentClassEntry,
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
        entry.char_class for entry in StartingEquipmentClassEntry.objects.filter(template=template)
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
    assert Shop.objects.filter(club=club).count() == 0
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
    assert set(result) == {"options", "starting_equipment"}
    assert result["starting_equipment"].template_created is True
