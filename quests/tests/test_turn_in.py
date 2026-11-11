import pytest

from ledger.models import LedgerEntry
from ledger.services import InsufficientItems, coin_balance, item_quantities
from player_characters.models import Character, Trade, TradeLine
from quests import services
from quests.models import QuestCompletion


def _ready(give, character, item, qty=3):
    give(character, item, qty)


@pytest.mark.story("Q1")
def test_success(quest, character, player, item, reward_item, give):
    give(character, item, 3)
    before = LedgerEntry.objects.count()
    services.turn_in(quest, character, player)
    new = LedgerEntry.objects.order_by("pk")[before:]
    assert sorted(e.kind for e in new) == ["quest_reward", "quest_turn_in"]
    assert all(e.created_by == player for e in new)
    assert QuestCompletion.objects.filter(quest=quest, character=character).count() == 1
    q = item_quantities(character)
    assert q[item.pk] == 1
    assert q[reward_item.pk] == 1
    assert coin_balance(character) == 1000


@pytest.mark.story("Q1")
def test_missing_items(quest, character, player, item, give):
    give(character, item, 1)
    before = LedgerEntry.objects.count()
    with pytest.raises(InsufficientItems):
        services.turn_in(quest, character, player)
    assert LedgerEntry.objects.count() == before
    assert QuestCompletion.objects.count() == 0


@pytest.mark.story("Q1")
def test_held_items_fail(quest, character, player, item, give, club, other_player):
    from accounts.models import Membership

    give(character, item, 2)
    other = Character.objects.create(
        club=club, owner=Membership.objects.get(user=other_player, club=club), name="Borin"
    )
    trade = Trade.objects.create(club=club, sender=character, receiver=other)
    assert trade.status == Trade.Status.REQUESTED
    TradeLine.objects.create(trade=trade, item=item, quantity=1, from_sender=True)
    before = LedgerEntry.objects.count()
    with pytest.raises(InsufficientItems):
        services.turn_in(quest, character, player)
    assert LedgerEntry.objects.count() == before
    assert QuestCompletion.objects.count() == 0


@pytest.mark.story("Q1")
def test_no_requirements(quest, character, player):
    quest.requirements.all().delete()
    with pytest.raises(services.QuestNotAllowed):
        services.turn_in(quest, character, player)


@pytest.mark.story("Q2")
def test_not_live(upcoming_quest, ended_quest, character, player, item, give):
    give(character, item, 5)
    for q in (upcoming_quest, ended_quest):
        with pytest.raises(services.QuestNotLive):
            services.turn_in(q, character, player)
    assert QuestCompletion.objects.count() == 0


@pytest.mark.story("Q2")
def test_edge_days(club, item, character, player, give):
    from datetime import date

    from quests.models import Quest, QuestRequirement, QuestReward

    d = date(2026, 6, 15)
    q = Quest.objects.create(club=club, name="Edge", start_date=d, end_date=d)
    QuestRequirement.objects.create(quest=q, item=item, quantity=1)
    QuestReward.objects.create(quest=q, coins=5)
    give(character, item, 2)
    services.turn_in(q, character, player, today=d)
    for bad in (date(2026, 6, 14), date(2026, 6, 16)):
        with pytest.raises(services.QuestNotLive):
            services.turn_in(q, character, player, today=bad)


@pytest.mark.story("Q3")
def test_limits(limited_quest, character, player, item, give, club, other_player):
    from accounts.models import Membership

    other = Character.objects.create(
        club=club, owner=Membership.objects.get(user=other_player, club=club), name="Borin"
    )
    give(character, item, 5)
    give(other, item, 5)
    assert services.completions_left(limited_quest) == 1
    services.turn_in(limited_quest, character, player)
    assert services.completions_left(limited_quest) == 0
    assert services.character_completions_left(limited_quest, character) == 0
    with pytest.raises(services.QuestLimitReached):
        services.turn_in(limited_quest, character, player)
    with pytest.raises(services.QuestLimitReached):
        services.turn_in(limited_quest, other, player)


@pytest.mark.story("Q3")
def test_per_character_only(limited_quest, character, player, item, give, club, other_player):
    from accounts.models import Membership

    limited_quest.max_completions = None
    limited_quest.save()
    other = Character.objects.create(
        club=club, owner=Membership.objects.get(user=other_player, club=club), name="Borin"
    )
    give(character, item, 5)
    give(other, item, 5)
    services.turn_in(limited_quest, character, player)
    with pytest.raises(services.QuestLimitReached):
        services.turn_in(limited_quest, character, player)
    services.turn_in(limited_quest, other, player)


@pytest.mark.story("Q3")
def test_no_limits(quest, character, player, item, give):
    give(character, item, 6)
    assert services.completions_left(quest) is None
    assert services.character_completions_left(quest, character) is None
    for _ in range(3):
        services.turn_in(quest, character, player)
    assert QuestCompletion.objects.count() == 3


@pytest.mark.story("Q4")
def test_other_club_character(quest, other_club, player, item):
    from accounts.models import Membership, User

    u = User.objects.create_user("x@example.com", password="pw", display_name="X")
    m = Membership.objects.create(user=u, club=other_club)
    c = Character.objects.create(club=other_club, owner=m, name="Zed")
    with pytest.raises(services.QuestNotAllowed):
        services.turn_in(quest, c, u)
