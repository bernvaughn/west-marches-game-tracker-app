"""Tests for U136: quest notice progress on the board."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from items.models import Item
from ledger.services import Line, record
from player_characters.models import Character
from quests.models import Quest, QuestCompletion, QuestRequirement

pytestmark = pytest.mark.story("U136")


def _index(client):
    return client.get(reverse("quests:index", args=["club-a"])).content.decode()


def _pack_url(club, character):
    return reverse("characters:print_session_pack", args=[club.slug, character.pk])


@pytest.fixture
def parchment(club):
    """Stacked item: 100 cp per 10 sheets."""
    return Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=100,
        value_units=10,
    )


def _make_quest(club, name, item, qty, **fields):
    quest = Quest.objects.create(club=club, name=name, start_date=timezone.localdate(), **fields)
    QuestRequirement.objects.create(quest=quest, item=item, quantity=qty)
    return quest


def test_short_quest_shows_have_of_need_and_more(login, player, character, quest, item, give):
    """Have 1 of 2 -> "1 of 2", "1 more", bar present, no Ready stamp."""
    give(character, item, 1)
    body = _index(login(player))
    assert "1 of 2" in body
    assert 'class="wm-notice-short"' in body
    assert "1 more" in body
    assert 'role="progressbar"' in body
    assert "Ready to turn in" not in body


def test_ready_quest_shows_full_rows_and_stamp(login, player, character, quest, item, give):
    """Have 2 of 2 -> "2 of 2", Ready stamp, no "more" paragraph."""
    give(character, item, 2)
    body = _index(login(player))
    assert "2 of 2" in body
    assert "Ready to turn in" in body
    assert 'class="wm-notice-short"' not in body


def test_done_quest_shows_done_stamp_no_progress(
    login, player, character, limited_quest, item, give
):
    """Completed limited quest -> Done stamp, no progress list."""
    QuestCompletion.objects.create(
        quest=limited_quest, character=character, date=timezone.localdate()
    )
    body = _index(login(player))
    assert "Done" in body
    assert "wm-notice-progress" not in body


def test_no_character_no_progress(login, player, quest):
    """Player without a selected character: no progress on any notice."""
    body = _index(login(player))
    assert "wm-notice-progress" not in body


def test_stacked_item_shows_unit_name(login, player, club, character, parchment, give):
    """Stacked requirement shows "have of need unit_name item"."""
    _make_quest(club, "Scribe's Task", parchment, 40)
    give(character, parchment, 20)
    body = _index(login(player))
    assert "20 of 40 sheet" in body and "Parchment" in body
    assert "wm-notice-progress" in body


def test_detail_notice_has_no_progress(login, player, character, quest, item, give):
    """Detail page notice keeps its own 'Has' table; no progress block."""
    give(character, item, 2)
    url = reverse("quests:detail", args=["club-a", quest.pk])
    body = login(player).get(url).content.decode()
    assert "wm-notice--large" in body
    assert "wm-notice-progress" not in body


def test_board_carries_questcompleted_trigger(login, player, quest):
    """The board partial still triggers a refresh after a turn-in."""
    body = _index(login(player))
    assert 'hx-trigger="questCompleted from:body"' in body


def test_index_adds_no_per_quest_query(login, player, club):
    """The index runs the same quest-related queries for 1 quest as for 3 (no N+1)."""

    def prefetch_counts():
        with CaptureQueriesContext(connection) as ctx:
            login(player).get(reverse("quests:index", args=["club-a"]))
        queries = [q["sql"] for q in ctx.captured_queries]
        return (
            sum(1 for q in queries if "quests_questrequirement" in q),
            sum(1 for q in queries if "quests_questreward" in q),
        )

    Quest.objects.create(club=club, name="First quest", start_date=timezone.localdate())
    one = prefetch_counts()
    Quest.objects.create(club=club, name="Second quest", start_date=timezone.localdate())
    Quest.objects.create(club=club, name="Third quest", start_date=timezone.localdate())
    three = prefetch_counts()
    assert one == three == (1, 1)


@pytest.mark.django_db
def test_print_pack_hides_progress(login, club, player, item):
    """Print Session Pack renders ready quests without a progress block."""
    owner = Membership.objects.get(user=player, club=club)
    character = Character.objects.create(club=club, owner=owner, name="Aria")
    quest = _make_quest(club, "Ready quest", item, 2)
    record(character, "award", [Line(item=item, quantity=2)], note="test award")
    body = login(player).get(_pack_url(club, character)).content.decode()
    assert quest.name in body
    assert "wm-notice-progress" not in body
