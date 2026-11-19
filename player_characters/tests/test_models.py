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


def test_starting_equipment_claimed_defaults_to_false(character):
    """starting_equipment_claimed exists on Character and defaults to False."""
    field = Character._meta.get_field("starting_equipment_claimed")
    assert field.default is False
    assert character.starting_equipment_claimed is False
