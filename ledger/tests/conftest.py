"""Fixtures for ledger tests."""

import pytest

from items.models import Item
from player_characters.models import Character


@pytest.fixture
def second_item(club):
    return Item.objects.create(club=club, name="Potion", value_cp=50)


@pytest.fixture
def funded(character):
    """A character with 1000 coins."""
    from ledger.services import Line, record

    record(character, "award", [Line(coins=1000)])
    return character


@pytest.fixture
def other_character(club, other_player):
    owner = other_player.memberships.get(club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")
