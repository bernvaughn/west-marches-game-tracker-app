"""Seeded bundled gear is stacked and can be used one unit at a time."""

import re

import pytest

from accounts.club_seeding import seed_new_club
from accounts.models import Club, Membership, User
from character_options.models import CharacterClass
from items.models import Item
from ledger.models import LedgerLine
from ledger.services import Line, item_quantities, record
from player_characters.models import Character
from shops.models import Shop, ShopStock
from shops.services import percent_price, sell_price
from starting_equipment.models import StartingEquipmentClassLine, StartingEquipmentTemplate
from starting_equipment.services import apply_starting_equipment

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def seeded(db):
    club = Club.objects.create(name="Seeded", slug="seeded")
    seed_new_club(club)
    return club


def test_arrows_seeded_as_stacked(seeded):
    arrows = Item.objects.get(club=seeded, name="Arrows")
    assert arrows.is_stacked
    assert arrows.unit_name == "arrow"
    assert arrows.value_units == 20
    assert arrows.value_cp == 100


def test_no_seeded_item_has_a_count_in_its_name(seeded):
    # Bundle counts like "(20)". Pack contents with measures, such as "Hempen rope (50 ft)",
    # are container slot items and are not bundles.
    bad = [i.name for i in Item.objects.filter(club=seeded) if re.search(r"\(\d+\)", i.name)]
    assert bad == [], bad


def test_general_store_sells_arrows_bundle_at_old_price(seeded):
    shop = Shop.objects.get(club=seeded, name="General Store")
    stock = ShopStock.objects.get(shop=shop, item__name="Arrows")
    assert stock.bundle_units == 20
    old_plain_price = percent_price(100, shop.sell_percent)  # "Arrows (20)" at 100 cp
    assert sell_price(stock) == old_plain_price == 100


def test_starting_equipment_for_bolt_class_is_stacked_units(seeded):
    assert not Item.objects.filter(club=seeded, name="Crossbow Bolt").exists()
    bolts = Item.objects.get(club=seeded, name="Crossbow Bolts")
    assert bolts.is_stacked and bolts.value_units == 20

    warlock = CharacterClass.objects.get(club=seeded, name="Warlock")
    lines = StartingEquipmentClassLine.objects.filter(class_entry__class_option=warlock)
    bolt_lines = [line for line in lines if line.item.name.startswith("Crossbow Bolt")]
    assert [(line.item_id, line.quantity) for line in bolt_lines] == [(bolts.pk, 20)]

    user = User.objects.create_user("w@example.com", password="pw", display_name="W")
    membership = Membership.objects.create(user=user, club=seeded)
    char = Character.objects.create(
        club=seeded, owner=membership, name="Wanda", class_option=warlock, level=1
    )
    template = StartingEquipmentTemplate.objects.get(club=seeded, is_active=True)
    apply_starting_equipment(char, template, None)
    assert item_quantities(char)[bolts.pk] == 20
    assert not LedgerLine.objects.filter(entry__character=char, item__name="Crossbow Bolt").exists()


def test_seeded_character_consumes_one_arrow_of_twenty(seeded):
    arrows = Item.objects.get(club=seeded, name="Arrows")
    user = User.objects.create_user("a@example.com", password="pw", display_name="A")
    membership = Membership.objects.create(user=user, club=seeded)
    char = Character.objects.create(club=seeded, owner=membership, name="Aria")
    record(char, "award", [Line(item=arrows, quantity=20)])
    record(char, "consumed", [Line(item=arrows, quantity=-1)])
    assert item_quantities(char)[arrows.pk] == 19
