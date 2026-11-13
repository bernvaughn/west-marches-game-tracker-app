from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Membership
from downtime.models import (
    DowntimeAction,
    DowntimeEntry,
    DowntimePointRequest,
)
from player_characters.models import Character


def _today():
    return timezone.localdate()


@pytest.fixture
def other_club_character(other_club):
    from accounts.models import User

    user = User.objects.create_user("x@example.com", password="pw", display_name="X")
    m = Membership.objects.create(user=user, club=other_club)
    return Character.objects.create(club=other_club, owner=m, name="Zed")


@pytest.fixture
def action(club):
    return DowntimeAction.objects.create(
        club=club, name="Work at a bakery", start_date=_today() - timedelta(days=1)
    )


@pytest.fixture
def upcoming_action(club):
    return DowntimeAction.objects.create(
        club=club, name="Upcoming", start_date=_today() + timedelta(days=5)
    )


@pytest.fixture
def ended_action(club):
    return DowntimeAction.objects.create(
        club=club, name="Ended", end_date=_today() - timedelta(days=5)
    )


@pytest.fixture
def other_club_action(other_club):
    return DowntimeAction.objects.create(club=other_club, name="Other")


@pytest.fixture
def entries(action):
    return [
        DowntimeEntry.objects.create(action=action, label="Bread", weight=3, coins=10, order=0),
        DowntimeEntry.objects.create(action=action, label="Nothing", weight=1, order=1),
    ]


@pytest.fixture
def entry(entries):
    return entries[0]


@pytest.fixture
def point_request(club, player, character):
    req = DowntimePointRequest.objects.create(
        club=club, requested_by=Membership.objects.get(user=player, club=club), points=1
    )
    req.characters.add(character)
    return req
