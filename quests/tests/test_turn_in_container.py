"""Tests for quest reward granting container unopened."""

import pytest
from django.urls import reverse

from items.models import ContainerOpening
from items.tests.factories import _get_or_create_item, add_slot, make_container
from ledger.services import Line, available_items, record
from quests.models import Quest, QuestRequirement, QuestReward


@pytest.fixture
def container_quest_chest(club):
    """Container for quest chest."""
    container = make_container(club, name="Quest Chest")
    sword = _get_or_create_item(club, "Quest Sword")
    add_slot(container, [(sword, 1, 1, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def quest_dragon_slayer(club, container_quest_chest):
    """Quest with container reward."""
    quest = Quest.objects.create(club=club, name="Dragon Slayer", start_date="2024-01-01")
    QuestReward.objects.create(quest=quest, item=container_quest_chest, quantity=1)
    scale = _get_or_create_item(club, "Dragon Scale")
    QuestRequirement.objects.create(quest=quest, item=scale, quantity=1)
    return quest


@pytest.mark.django_db
class TestQuestTurnInGrantsContainerUnopened:
    """Tests that quest turn-in grants container unopened."""

    def test_turn_in_with_container_reward_grants_unopened(
        self, client, club, game_master, character, quest_dragon_slayer
    ):
        """Turn in with container reward grants container unopened."""
        from quests.services import turn_in

        # Give character the requirement
        scale = _get_or_create_item(club, "Dragon Scale")
        record(character, "award", [Line(item=scale, quantity=1)], actor=game_master)

        # Turn in the quest
        turn_in(quest_dragon_slayer, character, actor=game_master)

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container_quest_chest.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        sword = _get_or_create_item(club, "Quest Sword")
        assert avail.get(sword.pk, 0) == 0

    def test_turn_in_with_container_reward_via_view(
        self, client, club, player, character, quest_dragon_slayer
    ):
        """Turn in via view with container reward grants container unopened."""
        from items.models import ContainerOpening
        from ledger.services import Line, available_items, record

        # Give character the requirement
        scale = _get_or_create_item(club, "Dragon Scale")
        record(character, "award", [Line(item=scale, quantity=1)], actor=player)

        client.force_login(player)
        url = reverse("quests:turn_in", args=[club.slug, quest_dragon_slayer.pk])
        response = client.post(url)
        assert response.status_code == 302

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container_quest_chest.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        sword = _get_or_create_item(club, "Quest Sword")
        assert avail.get(sword.pk, 0) == 0
