import pytest

from accounts.models import Membership
from items.models import Item
from ledger.services import Line, record
from player_characters.models import Character, Trade, TradeLine


@pytest.fixture
def second_item(club):
    return Item.objects.create(club=club, name="Torch", value_cp=1)


@pytest.fixture
def other_character(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.fixture
def funded(character, item):
    record(character, "award", [Line(coins=1000), Line(item=item, quantity=5)])
    return character


@pytest.fixture
def open_trade(club, character, other_character):
    def _make(status=Trade.Status.REQUESTED, sender=None, receiver=None, lines=()):
        trade = Trade.objects.create(
            club=club,
            sender=sender or character,
            receiver=receiver or other_character,
            status=status,
        )
        for kw in lines:
            TradeLine.objects.create(trade=trade, **kw)
        return trade

    return _make
