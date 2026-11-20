from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from ledger.templatetags.coins import coins as format_coins
from quests.models import Quest, QuestCompletion

pytestmark = pytest.mark.story("U48")


def _index(client):
    return client.get(reverse("quests:index", args=["club-a"])).content.decode()


def _split(body):
    board, _, down = body.partition("wm-taken-down")
    return board, down


def test_open_notice_content(login, player, quest, item):
    quest.description = "x" * 200
    quest.end_date = timezone.localdate() + timedelta(days=3)
    quest.save()
    board, _ = _split(_index(login(player)))
    assert "wm-notice" in board and quest.name in board
    assert "x" * 200 not in board and "x" * 135 in board
    assert format_coins(1000) in board
    assert f"2 x {item}" in board and "Ends" in board


def test_ready_stamp_follows_character(login, player, quest, character, item, give):
    c = login(player)
    assert "Ready to turn in" not in _index(c)
    give(character, item, 2)
    body = _index(c)
    assert "Ready to turn in" in body and f"Status for {character.name}" in body


def test_done_stamp_only_at_limit(login, player, limited_quest, quest, character, give, item):
    c = login(player)
    assert ">Done<" not in _index(c).replace("Done</span>", ">Done<")
    QuestCompletion.objects.create(
        quest=limited_quest, character=character, date=timezone.localdate()
    )
    assert "Done</span>" in _index(c)
    # quest without a per-character limit never shows Done
    QuestCompletion.objects.create(quest=quest, character=character, date=timezone.localdate())
    board, _ = _split(_index(c))
    assert quest.name in board and board.count("Done</span>") == 0


def test_taken_down_and_not_posted(
    login,
    player,
    character,
    game_master,
    club_admin,
    quest,
    ended_quest,
    upcoming_quest,
    limited_quest,
):
    QuestCompletion.objects.create(
        quest=limited_quest, character=character, date=timezone.localdate()
    )
    body = _index(login(player))
    board, down = _split(body)
    assert "<details" in body
    assert ended_quest.name in down and limited_quest.name in down
    assert ended_quest.name not in board and limited_quest.name not in board
    assert upcoming_quest.name not in body
    for user in (game_master, club_admin):
        _, down = _split(_index(login(user)))
        assert upcoming_quest.name in down and "Not posted yet" in down


def test_tilt_deterministic(login, player, quest):
    c = login(player)
    first = _index(c)
    assert f"wm-notice--tilt-{quest.pk % 5}" in first
    assert first.count("wm-notice--tilt-") == _index(c).count("wm-notice--tilt-")


def test_cross_club_never_shows(login, player, other_club_quest):
    assert other_club_quest.name not in _index(login(player))


def test_detail_notice_and_turn_in(login, player, quest, character, item, give):
    give(character, item, 2)
    c = login(player)
    url = reverse("quests:detail", args=["club-a", quest.pk])
    body = c.get(url).content.decode()
    assert "wm-notice--large" in body and "Ready to turn in" in body
    assert body.index("wm-notice--large") < body.index("Turn in as")
    assert "Edit quest" not in body
    c.post(reverse("quests:turn_in", args=["club-a", quest.pk]))
    assert Quest.objects.get(pk=quest.pk).completions.count() == 1
