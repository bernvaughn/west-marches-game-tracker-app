"""Loot preview on quest surfaces: the notice and the turn-in card (slice D2)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership
from player_characters.models import Character
from quests.models import Quest, QuestRequirement, QuestReward

pytestmark = pytest.mark.story("D2")


@pytest.fixture
def pack_quest(club, item, diplomats_pack):
    quest = Quest.objects.create(
        club=club, name="Envoy run", start_date=timezone.localdate() - timedelta(days=1)
    )
    QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
    QuestReward.objects.create(quest=quest, item=diplomats_pack, quantity=2)
    return quest


def _page(client, quest):
    resp = client.get(reverse("quests:detail", args=["club-a", quest.pk]))
    assert resp.status_code == 200
    body = resp.content.decode()
    notice, card = body.split('id="turn-in"', 1)
    return notice, card


def _gm_character(club, game_master):
    owner = Membership.objects.get(user=game_master, club=club)
    return Character.objects.create(club=club, owner=owner, name="GM hero")


def test_notice_keeps_reward_name_and_adds_preview(login, player, character, pack_quest):
    notice, _ = _page(login(player), pack_quest)
    assert "2 x" in notice
    assert "Diplomat&#x27;s Pack" in notice or "Diplomat's Pack" in notice
    assert "Preview contents" in notice
    assert "Fine clothes" in notice
    assert "One of" in notice
    assert "50% chance" in notice


def test_notice_masks_unknown_for_player(login, player, character, pack_quest):
    notice, _ = _page(login(player), pack_quest)
    assert "???" in notice
    assert "Sealed letter" not in notice


@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_notice_shows_unknown_to_gm_and_admin(request, login, club, pack_quest, who):
    user = request.getfixturevalue(who)
    notice, _ = _page(login(user), pack_quest)
    assert "Sealed letter" in notice


def test_turn_in_card_shows_preview_and_masks_for_player(login, player, character, pack_quest):
    _, card = _page(login(player), pack_quest)
    assert "Fine clothes" in card
    assert "???" in card
    assert "Sealed letter" not in card


def test_turn_in_card_shows_unknown_to_gm(login, club, game_master, pack_quest):
    _gm_character(club, game_master)
    _, card = _page(login(game_master), pack_quest)
    assert "Fine clothes" in card
    assert "Sealed letter" in card


def test_plain_reward_has_no_preview(login, player, character, club, item):
    from items.models import Item

    plain = Item.objects.create(club=club, name="Healing potion", value_cp=10)
    quest = Quest.objects.create(club=club, name="Plain", start_date=timezone.localdate())
    QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
    QuestReward.objects.create(quest=quest, item=plain, quantity=1)
    notice, card = _page(login(player), quest)
    assert "Healing potion" in notice
    assert "Preview contents" not in notice
    assert "wm-loot-preview" not in notice + card


def test_leak_sweep_player_page(login, player, character, pack_quest):
    resp = login(player).get(reverse("quests:detail", args=["club-a", pack_quest.pk]))
    assert "Sealed letter" not in resp.content.decode()
