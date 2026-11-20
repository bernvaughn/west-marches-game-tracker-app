"""Tests for loot preview on quest surfaces."""

import pytest
from django.urls import reverse

from items.tests.factories import make_container, add_slot, _get_or_create_item
from quests.tests.factories import QuestFactory, QuestRewardFactory, QuestRequirementFactory


@pytest.mark.django_db
class TestQuestNoticeLootPreview:
    """Tests for loot preview in quest notice."""

    def test_notice_shows_preview_for_container_reward(self, client, club, player, game_master):
        """Quest notice shows preview for container reward."""
        container = make_container(club, name="Treasure Chest")
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Gold Coins", qty_min=10, qty_max=20)

        quest = QuestFactory(club=club, name="Find the Chest")
        QuestRewardFactory(quest=quest, item=container, quantity=1)

        client.force_login(game_master)
        url = reverse("quests:detail", args=[club.slug, quest.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Treasure Chest" in content
        assert "Gold Coins" in content
        assert "10–20" in content or "10-20" in content

    def test_notice_masks_unknown_for_player(self, client, club, player):
        """Quest notice masks unknown items for player."""
        container = make_container(club, name="Mystery Reward")
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Secret Item", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Mystery Quest")
        QuestRewardFactory(quest=quest, item=container, quantity=1)

        client.force_login(player)
        url = reverse("quests:detail", args=[club.slug, quest.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "???" in content
        assert "Secret Item" not in content

    def test_notice_shows_real_name_for_gm(self, client, club, game_master):
        """Quest notice shows real name for GM."""
        container = make_container(club, name="Mystery Reward")
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Secret Item", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Mystery Quest")
        QuestRewardFactory(quest=quest, item=container, quantity=1)

        client.force_login(game_master)
        url = reverse("quests:detail", args=[club.slug, quest.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Secret Item" in content


@pytest.mark.django_db
class TestQuestTurnInCardLootPreview:
    """Tests for loot preview in quest turn-in card."""

    def test_turn_in_card_shows_preview_for_container_reward(self, client, club, player, game_master, character):
        """Turn-in card shows preview for container reward."""
        container = make_container(club, name="Reward Chest")
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=False)
        ContainerSlotOptionFactory(slot=slot, item__name="Magic Sword", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Defeat the Dragon")
        QuestRewardFactory(quest=quest, item=container, quantity=1)
        QuestRequirementFactory(quest=quest, item__name="Dragon Scale", quantity=1)

        client.force_login(game_master)
        url = reverse("quests:play", args=[club.slug, quest.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Reward Chest" in content
        assert "Magic Sword" in content

    def test_turn_in_card_masks_unknown_for_player(self, client, club, player, character):
        """Turn-in card masks unknown items for player."""
        container = make_container(club, name="Mystery Reward")
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Hidden Artifact", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Secret Quest")
        QuestRewardFactory(quest=quest, item=container, quantity=1)
        QuestRequirementFactory(quest=quest, item__name="Key", quantity=1)

        client.force_login(player)
        url = reverse("quests:play", args=[club.slug, quest.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "???" in content
        assert "Hidden Artifact" not in content

    def test_turn_in_card_shows_real_name_for_gm(self, client, club, game_master, character):
        """Turn-in card shows real name for GM."""
        container = make_container(club, name="Mystery Reward")
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Hidden Artifact", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Secret Quest")
        QuestRewardFactory(quest=quest, item=container, quantity=1)
        QuestRequirementFactory(quest=quest, item__name="Key", quantity=1)

        client.force_login(game_master)
        url = reverse("quests:play", args=[club.slug, quest.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Hidden Artifact" in content


@pytest.mark.django_db
class TestQuestLootPreviewLeakSweep:
    """Tests to ensure unknown item names never leak to player HTML on quest surfaces."""

    def test_notice_player_never_sees_hidden_artifact(self, client, club, player):
        """Player never sees 'Hidden Artifact' in quest notice HTML."""
        container = make_container(club, name="Mystery Reward")
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Hidden Artifact", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Secret Quest")
        QuestRewardFactory(quest=quest, item=container, quantity=1)

        client.force_login(player)
        url = reverse("quests:detail", args=[club.slug, quest.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Hidden Artifact" not in content

    def test_turn_in_card_player_never_sees_hidden_artifact(self, client, club, player, character):
        """Player never sees 'Hidden Artifact' in turn-in card HTML."""
        container = make_container(club, name="Mystery Reward")
        slot = ContainerSlotFactory(container=container, chance_pct=100, unknown=True)
        ContainerSlotOptionFactory(slot=slot, item__name="Hidden Artifact", qty_min=1, qty_max=1)

        quest = QuestFactory(club=club, name="Secret Quest")
        QuestRewardFactory(quest=quest, item=container, quantity=1)
        QuestRequirementFactory(quest=quest, item__name="Key", quantity=1)

        client.force_login(player)
        url = reverse("quests:play", args=[club.slug, quest.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Hidden Artifact" not in content