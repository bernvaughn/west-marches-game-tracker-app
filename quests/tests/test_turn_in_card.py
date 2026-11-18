import pytest
from django.urls import reverse
from django.utils import timezone

from quests.models import Quest, QuestCompletion


def _url(name, *args):
    return reverse(f"quests:{name}", args=["club-a", *args])


def _body(client, quest):
    return client.get(_url("detail", quest.pk)).content.decode()


@pytest.mark.story("U55")
def test_card_lists_counts_and_missing(login, player, quest, character, item, give):
    item.symbol = "X"
    item.save()
    give(character, item, 1)
    body = _body(login(player), quest)
    assert 'id="turn-in"' in body
    assert character.name in body
    assert "wm-item-symbol" in body
    assert "wm-quest-turnin-missing" in body
    assert "Missing" in body
    assert "disabled" in body.split('id="turn-in"')[1]


@pytest.mark.story("U55")
def test_enabled_when_ready_and_post_turns_in(login, player, quest, character, item, give):
    give(character, item, 2)
    c = login(player)
    card = _body(c, quest).split('id="turn-in"')[1]
    assert "disabled" not in card
    assert "OK" in card
    c.post(_url("turn_in", quest.pk))
    assert QuestCompletion.objects.filter(quest=quest).count() == 1


@pytest.mark.story("U55")
def test_disabled_when_full(login, player, quest, character, item, give, other_player, club):
    from accounts.models import Membership
    from player_characters.models import Character

    owner = Membership.objects.get(user=other_player, club=club)
    other = Character.objects.create(club=club, owner=owner, name="Other")
    give(character, item, 2)
    quest.max_completions = 1
    quest.save()
    QuestCompletion.objects.create(quest=quest, character=other, date=timezone.localdate())
    card = _body(login(player), quest).split('id="turn-in"')[1]
    assert "This quest is full." in card
    assert "disabled" in card


@pytest.mark.story("U55")
def test_disabled_when_limit_reached(login, player, quest, character, item, give):
    give(character, item, 4)
    quest.max_per_character = 1
    quest.save()
    c = login(player)
    c.post(_url("turn_in", quest.pk))
    card = _body(c, quest).split('id="turn-in"')[1]
    assert "maximum number of times" in card
    assert "disabled" in card


@pytest.mark.story("U55")
def test_no_character(login, other_player, club, quest):
    from accounts.models import Membership, User

    user = User.objects.create_user("nochar@example.com", password="x", display_name="N")
    Membership.objects.create(user=user, club=club)
    card = _body(login(user), quest).split('id="turn-in"')[1]
    assert "You have no character in this club." in card
    assert "Turn in as" not in card


@pytest.mark.story("U55")
def test_notice_icons_on_board_and_cross_club(login, player, quest, item, other_club_quest):
    item.symbol = "Z"
    item.save()
    c = login(player)
    assert "wm-item-symbol" in c.get(_url("index")).content.decode()
    assert "wm-item-symbol" in _body(c, quest)
    assert c.get(_url("detail", other_club_quest.pk)).status_code == 404
    assert other_club_quest.name not in c.get(_url("index")).content.decode()


@pytest.mark.story("U55")
def test_rewards_section_shown_when_quest_has_rewards(login, player, quest, character, item, give):
    give(character, item, 2)
    c = login(player)
    body = _body(c, quest)
    assert "wm-quest-rewards" in body
    assert "Rewards" in body


@pytest.mark.story("U55")
def test_rewards_show_coins_formatted_with_coins_filter(
    login, player, quest, character, item, give
):
    give(character, item, 2)
    c = login(player)
    body = _body(c, quest)
    assert "coin coin-" in body


@pytest.mark.story("U55")
def test_rewards_show_item_with_quantity_and_name(
    login, player, quest, character, item, reward_item, give
):
    give(character, item, 2)
    c = login(player)
    body = _body(c, quest)
    assert reward_item.name in body
    assert "×" in body


@pytest.mark.story("U55")
def test_rewards_section_hidden_when_no_rewards(login, player, club, character, item, give):
    quest = Quest.objects.create(club=club, name="No Reward Quest")
    from quests.models import QuestRequirement

    QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
    give(character, item, 1)
    c = login(player)
    body = _body(c, quest)
    assert "wm-quest-rewards" not in body


@pytest.mark.story("U55")
def test_rewards_read_only_no_interactive_elements(login, player, quest, character, item, give):
    give(character, item, 2)
    c = login(player)
    body = _body(c, quest)
    start = body.index('class="wm-quest-rewards"')
    end = body.index("<form", start)
    rewards_section = body[start:end]
    assert "<form" not in rewards_section
    assert "<button" not in rewards_section
    assert "<input" not in rewards_section
    assert "<a " not in rewards_section
