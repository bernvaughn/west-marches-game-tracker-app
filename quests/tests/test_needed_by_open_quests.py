import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from quests.models import QuestCompletion
from quests.services import needed_by_open_quests

pytestmark = [pytest.mark.story("U47"), pytest.mark.django_db]


def test_live_quest_included(character, quest, item):
    assert needed_by_open_quests(character) == {item.pk: [quest]}


def test_closed_quests_excluded(character, upcoming_quest, ended_quest, other_club_quest, item):
    assert needed_by_open_quests(character) == {}


def test_full_quests_excluded(character, limited_quest):
    QuestCompletion.objects.create(
        quest=limited_quest, character=character, date=limited_quest.start_date
    )
    assert needed_by_open_quests(character) == {}


def test_club_full_excluded_but_other_character_not(club, player, limited_quest, character):
    from accounts.models import Membership
    from player_characters.models import Character

    other = Character.objects.create(
        club=club, owner=Membership.objects.get(user=player, club=club), name="Other"
    )
    limited_quest.max_per_character = None
    limited_quest.save()
    QuestCompletion.objects.create(
        quest=limited_quest, character=other, date=limited_quest.start_date
    )
    assert needed_by_open_quests(character) == {}


def test_query_count_is_flat(club, character, item, quest):
    from quests.tests.conftest import _make

    with CaptureQueriesContext(connection) as few:
        needed_by_open_quests(character)
    for i in range(5):
        _make(club, f"More {i}", item)
    with CaptureQueriesContext(connection) as many:
        needed_by_open_quests(character)
    assert len(many) == len(few)
