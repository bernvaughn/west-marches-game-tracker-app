"""Tests for loot preview on quest surfaces."""

import pytest
from django.urls import reverse

from items.tests.factories import _get_or_create_item, add_slot, make_container
from quests.models import Quest, QuestRequirement, QuestReward


@pytest.fixture
def container_with_preview(club):
    """Create a container with preview content."""
    container = make_container(club, name="Treasure Chest")
    gold = _get_or_create_item(club, "Gold Coins")
    add_slot(container, [(gold, 10, 20, 1)], chance_pct=100, unknown=False)
    return container


@pytest.fixture
def container_unknown(club):
    """Create a container with unknown slot."""
    container = make_container(club, name="Mystery Reward")
    secret = _get_or_create_item(club, "Secret Item")
    add_slot(container, [(secret, 1, 1, 1)], chance_pct=100, unknown=True)
    return container


@pytest.fixture
def container_hidden_artifact(club):
    """Create a container with hidden artifact."""
    container = make_container(club, name="Mystery Reward")
    artifact = _get_or_create_item(club, "Hidden Artifact")
    add_slot(container, [(artifact, 1, 1, 1)], chance_pct=100, unknown=True)
    return container


@pytest.fixture
def quest_with_container_reward(club, container_with_preview):
    """Quest with container reward."""
    quest = Quest.objects.create(club=club, name="Find the Chest", start_date="2024-01-01")
    QuestReward.objects.create(quest=quest, item=container_with_preview, quantity=1)
    return quest


@pytest.fixture
def quest_with_unknown_reward(club, container_unknown):
    """Quest with unknown container reward."""
    quest = Quest.objects.create(club=club, name="Mystery Quest", start_date="2024-01-01")
    QuestReward.objects.create(quest=quest, item=container_unknown, quantity=1)
    return quest


@pytest.fixture
def quest_with_hidden_artifact(club, container_hidden_artifact):
    """Quest with hidden artifact reward."""
    quest = Quest.objects.create(club=club, name="Secret Quest", start_date="2024-01-01")
    QuestReward.objects.create(quest=quest, item=container_hidden_artifact, quantity=1)
    return quest


@pytest.fixture
def quest_for_turnin(club, container_with_preview):
    """Quest with container reward and requirement for turn-in."""
    quest = Quest.objects.create(club=club, name="Defeat the Dragon", start_date="2024-01-01")
    QuestReward.objects.create(quest=quest, item=container_with_preview, quantity=1)
    scale = _get_or_create_item(club, "Dragon Scale")
    QuestRequirement.objects.create(quest=quest, item=scale, quantity=1)
    return quest


@pytest.fixture
def quest_unknown_turnin(club, container_hidden_artifact):
    """Quest with unknown container reward for turn-in."""
    quest = Quest.objects.create(club=club, name="Secret Quest", start_date="2024-01-01")
    QuestReward.objects.create(quest=quest, item=container_hidden_artifact, quantity=1)
    key = _get_or_create_item(club, "Key")
    QuestRequirement.objects.create(quest=quest, item=key, quantity=1)
    return quest


@pytest.mark.django_db
class TestQuestNoticeLootPreview:
    """Tests for loot preview in quest notice."""

    def test_notice_shows_preview_for_container_reward(
        self, client, club, player, game_master, quest_with_container_reward
    ):
        """Quest notice shows preview for container reward."""
        client.force_login(game_master)
        url = reverse("quests:detail", args=[club.slug, quest_with_container_reward.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Treasure Chest" in content
        assert "Gold Coins" in content
        assert "10–20" in content or "10-20" in content

    def test_notice_masks_unknown_for_player(self, client, club, player, quest_with_unknown_reward):
        """Quest notice masks unknown items for player."""
        client.force_login(player)
        url = reverse("quests:detail", args=[club.slug, quest_with_unknown_reward.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "???" in content
        assert "Secret Item" not in content

    def test_notice_shows_real_name_for_gm(
        self, client, club, game_master, quest_with_unknown_reward
    ):
        """Quest notice shows real name for GM."""
        client.force_login(game_master)
        url = reverse("quests:detail", args=[club.slug, quest_with_unknown_reward.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Secret Item" in content


@pytest.mark.django_db
class TestQuestTurnInCardLootPreview:
    """Tests for loot preview in quest turn-in card."""

    def test_turn_in_card_shows_preview_for_container_reward(
        self, client, club, player, game_master, character, quest_for_turnin
    ):
        """Turn-in card shows preview for container reward."""
        client.force_login(game_master)
        url = reverse("quests:play", args=[club.slug, quest_for_turnin.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Treasure Chest" in content
        assert "Gold Coins" in content

    def test_turn_in_card_masks_unknown_for_player(
        self, client, club, player, character, quest_unknown_turnin
    ):
        """Turn-in card masks unknown items for player."""
        client.force_login(player)
        url = reverse("quests:play", args=[club.slug, quest_unknown_turnin.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "???" in content
        assert "Hidden Artifact" not in content

    def test_turn_in_card_shows_real_name_for_gm(
        self, client, club, game_master, character, quest_unknown_turnin
    ):
        """Turn-in card shows real name for GM."""
        client.force_login(game_master)
        url = reverse("quests:play", args=[club.slug, quest_unknown_turnin.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Hidden Artifact" in content


@pytest.mark.django_db
class TestQuestLootPreviewLeakSweep:
    """Tests to ensure unknown item names never leak to player HTML on quest surfaces."""

    def test_notice_player_never_sees_hidden_artifact(
        self, client, club, player, quest_with_hidden_artifact
    ):
        """Player never sees 'Hidden Artifact' in quest notice HTML."""
        client.force_login(player)
        url = reverse("quests:detail", args=[club.slug, quest_with_hidden_artifact.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Hidden Artifact" not in content

    def test_turn_in_card_player_never_sees_hidden_artifact(
        self, client, club, player, character, quest_unknown_turnin
    ):
        """Player never sees 'Hidden Artifact' in turn-in card HTML."""
        client.force_login(player)
        url = reverse("quests:play", args=[club.slug, quest_unknown_turnin.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Hidden Artifact" not in content
