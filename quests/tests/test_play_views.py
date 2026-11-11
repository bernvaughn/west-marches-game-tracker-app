import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts.models import Club, Membership, User
from ledger.services import coin_balance
from ledger.templatetags.coins import coins as format_coins
from player_characters.models import Character
from quests import services
from quests.models import QuestCompletion


def _url(name, *args):
    return reverse(f"quests:{name}", args=["club-a", *args])


@pytest.mark.story("Q2")
def test_index_lists_live_only(login, player, quest, upcoming_quest, ended_quest, other_club_quest):
    r = login(player).get(_url("index"))
    body = r.content.decode()
    assert quest.name in body
    assert format_coins(1000) in body
    for q in (upcoming_quest, ended_quest, other_club_quest):
        assert q.name not in body


@pytest.mark.story("Q2")
def test_detail_404_not_live(login, player, upcoming_quest, ended_quest, character, item, give):
    c = login(player)
    for q in (upcoming_quest, ended_quest):
        assert c.get(_url("detail", q.pk)).status_code == 404
    give(character, item, 5)
    c.post(_url("turn_in", upcoming_quest.pk), {"character": character.pk})
    assert QuestCompletion.objects.count() == 0


@pytest.mark.story("Q4")
def test_other_club_404(login, player, other_club_quest, quest, other_club):
    c = login(player)
    assert c.get(_url("detail", other_club_quest.pk)).status_code == 404
    assert c.post(_url("turn_in", other_club_quest.pk), {"character": "1"}).status_code == 404
    u = User.objects.create_user("x@example.com", password="pw", display_name="X")
    m = Membership.objects.create(user=u, club=other_club)
    foreign = Character.objects.create(club=other_club, owner=m, name="Zed")
    assert c.post(_url("turn_in", quest.pk), {"character": foreign.pk}).status_code == 404


@pytest.mark.story("Q1")
def test_owner_turn_in(login, player, quest, character, item, give):
    give(character, item, 2)
    r = login(player).post(_url("turn_in", quest.pk), {"character": character.pk})
    assert r.status_code == 302
    assert QuestCompletion.objects.count() == 1
    assert coin_balance(character) == 1000


@pytest.mark.story("Q1")
def test_not_owner_and_blank(login, player, other_player, quest, character, item, give):
    give(character, item, 2)
    r = login(other_player).post(_url("turn_in", quest.pk), {"character": character.pk})
    assert r.status_code == 404
    r = login(player).post(_url("turn_in", quest.pk), {"character": ""})
    assert r.status_code == 302
    assert QuestCompletion.objects.count() == 0


@pytest.mark.story("Q1")
def test_missing_message(login, player, quest, character):
    c = login(player)
    r = c.post(_url("turn_in", quest.pk), {"character": character.pk}, follow=True)
    assert "Missing 2 x Rope" in r.content.decode()
    assert QuestCompletion.objects.count() == 0


@pytest.mark.story("Q1")
def test_detail_ready_and_missing(login, player, quest, character, item, give):
    c = login(player)
    assert "Missing 2 x Rope" in c.get(_url("detail", quest.pk)).content.decode()
    give(character, item, 2)
    assert "Ready" in c.get(_url("detail", quest.pk)).content.decode()


@pytest.mark.story("Q1")
def test_demo_player_completes(db):
    call_command("seed_demo")
    call_command("seed_demo")
    club = Club.objects.get()
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    assert coin_balance(aria) == 5000
    from quests.models import Quest

    quest = Quest.objects.get(club=club, name="Pelts for the Tanner")
    services.turn_in(quest, aria, aria.owner.user)
    assert coin_balance(aria) == 6000
