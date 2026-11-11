import pytest

from accounts.models import Membership, User
from items.models import Item
from ledger.services import Line, record
from player_characters.models import Character, Trade, TradeLine


@pytest.fixture
def other_character(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Bram")


@pytest.fixture
def third_character(club, game_master):
    owner = Membership.objects.get(user=game_master, club=club)
    return Character.objects.create(club=club, owner=owner, name="Cyra")


@pytest.fixture
def foreign_character(other_club):
    user = User.objects.create_user("foreign@example.com", password="pw", display_name="Foreign")
    owner = Membership.objects.create(user=user, club=other_club)
    return Character.objects.create(club=other_club, owner=owner, name="Zed")


@pytest.fixture
def foreign_item(other_club):
    return Item.objects.create(club=other_club, name="Foreign gem", value_cp=50)


@pytest.fixture
def give():
    def _give(character, item=None, quantity=0, coins=0):
        lines = []
        if item is not None:
            lines.append(Line(item=item, quantity=quantity))
        if coins:
            lines.append(Line(coins=coins))
        return record(character, "award", lines, note="test award")

    return _give


@pytest.fixture
def make_trade():
    """Create a Trade and its lines directly.

    Each entry in `lines` is a `(from_sender, Line)` tuple.
    """

    def _make(sender, receiver, lines=(), note="", status="requested"):
        trade = Trade.objects.create(
            club=sender.club, sender=sender, receiver=receiver, note=note, status=status
        )
        for from_sender, line in lines:
            TradeLine.objects.create(
                trade=trade,
                from_sender=from_sender,
                item=line.item,
                quantity=line.quantity,
                coins=line.coins,
            )
        return trade

    return _make
