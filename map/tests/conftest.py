import pytest

from accounts.models import Membership, User
from map.models import HexMap, Location, Tile
from player_characters.models import Character


@pytest.fixture
def hex_map(club):
    return HexMap.objects.create(club=club, name="The Marches")


@pytest.fixture
def other_map(other_club):
    return HexMap.objects.create(club=other_club, name="Foreign Lands")


@pytest.fixture
def tile_location(hex_map):
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    return Location.objects.create(
        tile=tile,
        name="Old Watchtower",
        color="red",
        symbol="T",
        player_notes="Player note text",
        gm_notes="Secret GM note",
        target_band="1-2",
    )


@pytest.fixture
def player_character(character):
    return character


@pytest.fixture
def second_character(club, player):
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.fixture
def other_character(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Cael")


@pytest.fixture
def other_club_member(other_club):
    user = User.objects.create_user("outsider@example.com", password="pw", display_name="Out")
    Membership.objects.create(user=user, club=other_club)
    return user
