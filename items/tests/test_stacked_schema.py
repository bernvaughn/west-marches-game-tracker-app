"""Schema tests for the stacked-item fields and CHECK constraints (U123)."""

import io

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from items.models import Item
from items.tests.factories import make_arrows, make_parchment, make_rope


@pytest.mark.story("U123")
@pytest.mark.django_db
def test_plain_item_defaults(db, club):
    item = Item.objects.create(club=club, name="Sword", value_cp=100)
    assert item.is_stacked is False
    assert item.unit_name == ""
    assert item.value_units == 1


@pytest.mark.story("U123")
@pytest.mark.django_db
def test_stacked_plus_container_raises(club):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Item.objects.create(
                club=club,
                name="Chest",
                is_stacked=True,
                is_container=True,
                unit_name="slot",
                value_units=1,
            )


@pytest.mark.story("U123")
@pytest.mark.django_db
def test_value_units_zero_raises(club):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Item.objects.create(
                club=club,
                name="Bad",
                is_stacked=True,
                unit_name="sheet",
                value_units=0,
            )


@pytest.mark.story("U123")
@pytest.mark.django_db
def test_stacked_blank_unit_name_raises(club):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Item.objects.create(
                club=club,
                name="Bad",
                is_stacked=True,
                unit_name="",
                value_units=1,
            )


@pytest.mark.story("U123")
@pytest.mark.django_db
def test_valid_stacked_item_saves(club):
    item = Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=100,
        value_units=10,
    )
    assert item.is_stacked is True
    assert item.unit_name == "sheet"
    assert item.value_units == 10


@pytest.mark.story("U123")
@pytest.mark.django_db
def test_factories_make_the_three_stacked_items(club):
    parchment = make_parchment(club)
    rope = make_rope(club)
    arrows = make_arrows(club)
    assert parchment.unit_name == "sheet" and parchment.value_units == 10
    assert rope.unit_name == "ft" and rope.value_units == 50
    assert arrows.unit_name == "arrow" and arrows.value_units == 20
    assert all(i.is_stacked for i in (parchment, rope, arrows))


@pytest.mark.story("U123")
@pytest.mark.django_db
def test_migrations_are_complete(db):
    """``makemigrations --check --dry-run`` must be clean: no model change
    is missing a migration and no migration touches another app."""
    out = io.StringIO()
    call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
    assert "No changes detected" in out.getvalue()
