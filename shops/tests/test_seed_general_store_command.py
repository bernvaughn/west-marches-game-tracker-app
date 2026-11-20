"""Tests for the seed_general_store management command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from items.models import Item
from shops.models import Shop, ShopStock

pytestmark = pytest.mark.django_db


def test_seed_general_store_command_creates_shop(club):
    """Command creates the General Store for an existing club."""
    out = StringIO()
    call_command("seed_general_store", "--club", club.slug, stdout=out)

    shop = Shop.objects.get(club=club, name="General Store")
    assert shop.keeper_name == "Mabel Packwell"
    assert shop.sell_percent == 100
    assert shop.buy_percent == 75
    assert shop.street_position == 0

    assert "Created General Store" in out.getvalue()
    assert "new items" in out.getvalue()


def test_seed_general_store_command_idempotent(club):
    """Second run changes nothing."""
    out1 = StringIO()
    call_command("seed_general_store", "--club", club.slug, stdout=out1)

    item_count_1 = Item.objects.filter(club=club).count()
    stock_count_1 = ShopStock.objects.filter(shop__club=club).count()

    out2 = StringIO()
    call_command("seed_general_store", "--club", club.slug, stdout=out2)

    item_count_2 = Item.objects.filter(club=club).count()
    stock_count_2 = ShopStock.objects.filter(shop__club=club).count()

    assert item_count_2 == item_count_1
    assert stock_count_2 == stock_count_1
    assert "already exists, nothing changed" in out2.getvalue()


def test_seed_general_store_command_unknown_club_raises_error():
    """Unknown club slug raises CommandError."""
    with pytest.raises(CommandError) as exc:
        call_command("seed_general_store", "--club", "nonexistent")
    assert "does not exist" in str(exc.value)


def test_seed_general_store_command_missing_club_arg_raises_error():
    """Missing --club argument raises error."""
    with pytest.raises(CommandError) as exc:
        call_command("seed_general_store")
    assert "required" in str(exc.value).lower() or "club" in str(exc.value).lower()


def test_seed_general_store_command_deleted_shop_not_auto_restored(club):
    """A deleted shop does not return unless command is run again."""
    # Seed once
    call_command("seed_general_store", "--club", club.slug)

    # Delete the shop
    Shop.objects.filter(club=club, name="General Store").delete()

    # Club now has no General Store
    assert not Shop.objects.filter(club=club, name="General Store").exists()

    # Running the command again recreates it
    out = StringIO()
    call_command("seed_general_store", "--club", club.slug, stdout=out)

    assert Shop.objects.filter(club=club, name="General Store").exists()
    assert "Created General Store" in out.getvalue()


def test_seed_general_store_command_touches_only_named_club(club, other_club):
    """Items in other clubs are not affected."""
    call_command("seed_general_store", "--club", club.slug)

    assert Shop.objects.filter(club=club, name="General Store").exists()
    assert not Shop.objects.filter(club=other_club, name="General Store").exists()
