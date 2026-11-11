import pytest
from django.core.exceptions import ValidationError

from accounts.models import Membership
from player_characters.models import Character

pytestmark = pytest.mark.story("FOUNDATION")


def test_character_owner_must_be_in_club(club, other_club, player):
    owner = Membership.objects.get(user=player, club=club)
    c = Character(club=other_club, owner=owner, name="X")
    with pytest.raises(ValidationError):
        c.clean()
    Character(club=club, owner=owner, name="X").clean()
