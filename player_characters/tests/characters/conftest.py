import pytest

from accounts.models import Membership, User
from items.models import Item
from ledger.services import Line, record
from player_characters.models import Character, Trade, TradeLine


def _character(club, user, name):
    owner = Membership.objects.get(user=user, club=club)
    return Character.objects.create(club=club, owner=owner, name=name)


@pytest.fixture
def second_character(club, player):
    return _character(club, player, "Brannoc")


@pytest.fixture
def other_character(club, other_player):
    return _character(club, other_player, "Borin")


@pytest.fixture
def gm_character(club, game_master):
    return _character(club, game_master, "Gwen")


@pytest.fixture
def foreign_member(other_club):
    user = User.objects.create_user("foreign@example.com", password="pw", display_name="Foreign")
    Membership.objects.create(user=user, club=other_club)
    return user


@pytest.fixture
def foreign_character(other_club, foreign_member):
    return _character(other_club, foreign_member, "Fenn")


@pytest.fixture
def foreign_item(other_club):
    return Item.objects.create(club=other_club, name="Foreign Rope", value_cp=100)


@pytest.fixture
def second_item(club):
    return Item.objects.create(club=club, name="Torch", value_cp=1)


@pytest.fixture
def funded(character, item):
    record(character, "award", [Line(coins=1000), Line(item=item, quantity=5)])
    return character


@pytest.fixture
def make_open_trade(club, character, other_character):
    def _make(*, sender=None, receiver=None, coins=0, items=None, status=Trade.Status.REQUESTED):
        trade = Trade.objects.create(
            club=club,
            sender=sender or character,
            receiver=receiver or other_character,
            status=status,
        )
        if coins:
            TradeLine.objects.create(trade=trade, from_sender=True, coins=coins)
        for it, qty in (items or {}).items():
            TradeLine.objects.create(trade=trade, from_sender=True, item=it, quantity=qty)
        return trade

    return _make
