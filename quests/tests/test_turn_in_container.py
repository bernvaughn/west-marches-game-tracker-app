"""Tests for quest reward granting container unopened."""

import pytest
from django.urls import reverse

from items.tests.factories import (
    ItemFactory,
    ContainerSlotFactory,
    ContainerSlotOptionFactory,
)
from quests.tests.factories import QuestFactory, QuestRewardFactory, QuestRequirementFactory
from accounts.tests.factories import UserFactory, ClubFactory, CharacterFactory


@pytest.mark.django_db
class TestQuestTurnInGrantsContainerUnopened:
    """Tests that quest turn-in grants container unopened."""

    def test_turn_in_with_container_reward_grants_unopened(self, client, club, gm_user, character):
        """Turn in with container reward grants container unopened."""
        from quests.services import turn_in
        from ledger.services import available_items
        from items.models import ContainerOpening

        container = ItemFactory(club=club, name="Quest Chest", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Quest Sword", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Dragon Slayer")
        QuestRewardFactory(quest=quest, item=container, quantity=1)
        QuestRequirementFactory(quest=quest, item__name="Dragon Scale", quantity=1)

        # Give character the requirement
        from ledger.services import record, Line
        scale = ItemFactory(club=club, name="Dragon Scale")
        record(character, "award", [Line(item=scale, quantity=1)], actor=gm_user)

        # Turn in the quest
        turn_in(quest, character, actor=gm_user)

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        sword = ItemFactory(club=club, name="Quest Sword")
        assert avail.get(sword.pk, 0) == 0

    def test_turn_in_with_container_reward_via_view(self, client, club, user, character):
        """Turn in via view with container reward grants container unopened."""
        from ledger.services import available_items, record, Line
        from items.models import ContainerOpening

        container = ItemFactory(club=club, name="Quest Chest", is_container=True)
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Quest Sword", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Dragon Slayer")
        QuestRewardFactory(quest=quest, item=container, quantity=1)
        QuestRequirementFactory(quest=quest, item__name="Dragon Scale", quantity=1)

        # Give character the requirement
        scale = ItemFactory(club=club, name="Dragon Scale")
        record(character, "award", [Line(item=scale, quantity=1)], actor=user)

        client.force_login(user)
        url = reverse("quests:turn_in", args=[club.slug, quest.pk])
        response = client.post(url)
        assert response.status_code == 302

        # Check ledger: one line for container +1
        avail = available_items(character)
        assert avail[container.pk] == 1

        # No ContainerOpening created
        assert not ContainerOpening.objects.filter(character=character).exists()

        # Contents not in inventory
        sword = ItemFactory(club=club, name="Quest Sword")
        assert avail.get(sword.pk, 0) == 0