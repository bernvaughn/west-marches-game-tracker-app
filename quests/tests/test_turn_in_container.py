"""A quest reward grants a container unopened (slice D2)."""

import pytest
from django.urls import reverse

from items.models import ContainerOpening, Item
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import available_items
from quests import services
from quests.models import QuestReward

pytestmark = pytest.mark.story("D2")


def _assert_unopened(character, container, qty):
    have = available_items(character)
    assert have[container.pk] == qty
    assert not LedgerEntry.objects.filter(character=character, kind="opened").exists()
    assert not ContainerOpening.objects.exists()
    content = Item.objects.filter(container_option_uses__slot__container=container).distinct()
    for item in content:
        assert have.get(item.pk, 0) == 0


@pytest.fixture
def pack_reward(quest, diplomats_pack):
    return QuestReward.objects.create(quest=quest, item=diplomats_pack, quantity=2)


def test_service_grants_container_unopened(
    quest, character, player, item, give, diplomats_pack, pack_reward
):
    give(character, item, 2)
    services.turn_in(quest, character, player)
    lines = LedgerLine.objects.filter(entry__character=character, item=diplomats_pack)
    assert [(ln.entry.kind, ln.quantity) for ln in lines] == [("quest_reward", 2)]
    _assert_unopened(character, diplomats_pack, 2)


def test_view_grants_container_unopened(
    login, quest, character, player, item, give, diplomats_pack, pack_reward
):
    give(character, item, 2)
    resp = login(player).post(reverse("quests:turn_in", args=["club-a", quest.pk]))
    assert resp.status_code == 302
    _assert_unopened(character, diplomats_pack, 2)
