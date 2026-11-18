"""Tests for starting equipment applied on character creation."""

import pytest
from django.urls import reverse

from items.models import Item
from ledger.models import LedgerEntry
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentTemplate,
)

pytestmark = [pytest.mark.django_db]


def create_url(club):
    return reverse("characters:create", kwargs={"club_slug": club.slug})


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def make_template(club, *, is_active=True):
    return StartingEquipmentTemplate.objects.create(
        club=club, name="Test Template", is_active=is_active
    )


def make_class_entry(template, *, char_class="Fighter", coins_cp=1000):
    return StartingEquipmentClassEntry.objects.create(
        template=template,
        char_class=char_class,
        min_level=1,
        max_level=20,
        coins_cp=coins_cp,
    )


def make_class_line(class_entry, item):
    return StartingEquipmentClassLine.objects.create(
        class_entry=class_entry, item=item, quantity=1, is_choice=False
    )


def make_bg_entry(template, *, background="Acolyte", coins_cp=500):
    return StartingEquipmentBackgroundEntry.objects.create(
        template=template, background=background, coins_cp=coins_cp
    )


def make_bg_line(bg_entry, item):
    return StartingEquipmentBackgroundLine.objects.create(
        background_entry=bg_entry, item=item, quantity=1, is_choice=False
    )


@pytest.fixture
def active_template(club):
    return make_template(club, is_active=True)


@pytest.fixture
def inactive_template(club):
    return make_template(club, is_active=False)


class TestCreateWithStartingEquipment:
    def test_background_saved_and_redirects_with_trigger(
        self, club, login, player, active_template
    ):
        """Creation with background saves background and redirects with the trigger."""
        client = login(player)
        response = client.post(
            create_url(club),
            {"name": "Aria", "char_class": "Fighter", "background": "Acolyte"},
        )
        assert response.status_code == 302

        character = Character.objects.get(name="Aria")
        assert character.background == "Acolyte"
        assert character.club == club
        assert response.url == f"{detail_url(club, character)}?starting_equipment=1"

    def test_grants_class_and_background_items_and_coins(
        self, club, login, player, active_template
    ):
        """Creation grants class + background items and coins in a single award entry."""
        longsword = Item.objects.create(club=club, name="Longsword", value_cp=1500)
        holy_symbol = Item.objects.create(club=club, name="Holy Symbol", value_cp=500)
        class_entry = make_class_entry(active_template, coins_cp=1000)
        make_class_line(class_entry, longsword)
        bg_entry = make_bg_entry(active_template, coins_cp=500)
        make_bg_line(bg_entry, holy_symbol)

        client = login(player)
        response = client.post(
            create_url(club),
            {"name": "Aria", "char_class": "Fighter", "background": "Acolyte"},
        )
        assert response.status_code == 302

        character = Character.objects.get(name="Aria")
        entries = LedgerEntry.objects.filter(character=character)
        assert entries.count() == 1
        entry = entries.first()
        assert entry.kind == LedgerEntry.Kind.AWARD
        assert entry.note == "Starting equipment"
        assert entry.created_by == player

        lines = entry.lines.select_related("item")
        item_lines = [line for line in lines if line.item is not None]
        assert {line.item.name for line in item_lines} == {"Longsword", "Holy Symbol"}
        coin_lines = [line for line in lines if line.coins != 0]
        assert sum(line.coins for line in coin_lines) == 1500

    def test_no_active_template_still_creates_and_redirects(
        self, club, login, player, inactive_template
    ):
        """No active template: creation still succeeds, no ledger entry, still triggers."""
        client = login(player)
        response = client.post(
            create_url(club),
            {"name": "Aria", "char_class": "Fighter", "background": "Acolyte"},
        )
        assert response.status_code == 302

        character = Character.objects.get(name="Aria")
        assert character.background == "Acolyte"
        assert response.url == f"{detail_url(club, character)}?starting_equipment=1"
        assert LedgerEntry.objects.count() == 0
