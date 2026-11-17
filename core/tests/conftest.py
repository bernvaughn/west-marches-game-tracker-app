"""Shared fixtures for core tests."""

import pytest

from accounts.models import Membership, User
from player_characters.models import Character


@pytest.fixture
def other_character(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Borin")


@pytest.fixture
def other_club_character(other_club):
    user = User.objects.create_user("x@example.com", password="pw", display_name="X")
    m = Membership.objects.create(user=user, club=other_club)
    return Character.objects.create(club=other_club, owner=m, name="Zed")