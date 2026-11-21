"""Tests for stacked items in quests."""

import pytest
from django.urls import reverse

from items.models import Item
from ledger.services import Line, available_items, record
from quests.models import Quest, QuestCompletion, QuestRequirement, QuestReward


@pytest.fixture
def parchment(club):
    """Stacked item: 100 cp per 10 sheets."""
    return Item.objects.create(
        club=club,
        name="Parchment",
        is_stacked=True,
        unit_name="sheet",
        value_cp=100,
        value_units=10,
    )


@pytest.fixture
def rope(club):
    """Stacked item: 100 cp per 50 ft."""
    return Item.objects.create(
        club=club,
        name="Rope",
        is_stacked=True,
        unit_name="ft",
        value_cp=100,
        value_units=50,
    )


@pytest.fixture
def quest_with_stacked_req(club, parchment):
    """Quest requiring 20 sheets of parchment."""
    quest = Quest.objects.create(
        club=club,
        name="Scribe's Task",
        start_date="2024-01-01",
    )
    QuestRequirement.objects.create(quest=quest, item=parchment, quantity=20)
    return quest


@pytest.fixture
def quest_with_stacked_reward(club, parchment):
    """Quest rewarding 2 sheets of parchment."""
    quest = Quest.objects.create(
        club=club,
        name="Scribe's Reward",
        start_date="2024-01-01",
    )
    # Need at least one requirement for turn_in to work
    QuestRequirement.objects.create(quest=quest, item=parchment, quantity=1)
    QuestReward.objects.create(quest=quest, item=parchment, quantity=2)
    return quest


@pytest.mark.django_db
class TestQuestStackedRequirements:
    """Tests for quest requirements with stacked items."""

    def test_require_20_sheets_has_19_refused(
        self, login, player, character, quest_with_stacked_req, parchment
    ):
        """Has 19 sheets -> turn-in refused, ledger unchanged."""
        record(character, "award", [Line(item=parchment, quantity=19)], note="Initial")
        c = login(player)

        url = reverse("quests:turn_in", args=["club-a", quest_with_stacked_req.pk])
        r = c.post(url, {"character": character.pk}, follow=True)

        assert r.status_code == 200
        assert "Missing" in r.content.decode()
        assert "1 sheet Parchment" in r.content.decode() or "1 sheet" in r.content.decode()
        # No completion created
        assert QuestCompletion.objects.filter(quest=quest_with_stacked_req).count() == 0
        # Ledger unchanged
        assert available_items(character)[parchment.pk] == 19

    def test_require_20_sheets_has_25_succeeds_5_left(
        self, login, player, character, quest_with_stacked_req, parchment
    ):
        """Has 25 sheets -> 5 left after turn-in."""
        record(character, "award", [Line(item=parchment, quantity=25)], note="Initial")
        c = login(player)

        url = reverse("quests:turn_in", args=["club-a", quest_with_stacked_req.pk])
        r = c.post(url, {"character": character.pk}, follow=True)

        assert r.status_code == 200
        # Completion created
        assert QuestCompletion.objects.filter(quest=quest_with_stacked_req).count() == 1
        # 5 left
        assert available_items(character)[parchment.pk] == 5

    def test_reward_2_sheets_arrives_as_2_units(
        self, login, player, character, quest_with_stacked_reward, parchment
    ):
        """Reward of 2 sheets arrives as 2 units."""
        # Give character the required 1 parchment
        record(character, "award", [Line(item=parchment, quantity=1)], note="Initial")
        c = login(player)

        url = reverse("quests:turn_in", args=["club-a", quest_with_stacked_reward.pk])
        r = c.post(url, {"character": character.pk}, follow=True)

        assert r.status_code == 200
        assert QuestCompletion.objects.filter(quest=quest_with_stacked_reward).count() == 1
        # Net: -1 (requirement) + 2 (reward) = +1, but requirement is consumed
        # Actually: starts with 1, gives 1 for requirement, gets 2 reward = 2 total
        assert available_items(character)[parchment.pk] == 2

    def test_unit_names_shown_on_quest_page(
        self, login, player, character, quest_with_stacked_req, parchment
    ):
        """Unit names shown on quest page, notice and turn-in card."""
        c = login(player)

        # Quest detail page
        url = reverse("quests:detail", args=["club-a", quest_with_stacked_req.pk])
        r = c.get(url)

        assert r.status_code == 200
        content = r.content.decode()
        # Should show unit name next to item name in requirements ("20 sheet Parchment")
        assert "20 sheet" in content and "Parchment" in content
        # Should show in turn-in card
        assert "Needed" in content or "Has" in content

    def test_reward_note_names_unit(
        self, login, player, character, quest_with_stacked_reward, parchment
    ):
        """Reward note names unit."""
        # Give character the required 1 parchment
        record(character, "award", [Line(item=parchment, quantity=1)], note="Initial")
        c = login(player)

        url = reverse("quests:turn_in", args=["club-a", quest_with_stacked_reward.pk])
        r = c.post(url, {"character": character.pk}, follow=True)

        assert r.status_code == 200
        from ledger.models import LedgerEntry

        reward_entry = LedgerEntry.objects.filter(character=character, kind="quest_reward").latest(
            "date"
        )
        assert "2 sheet Parchment" in reward_entry.note

    def test_other_club_character_refused(
        self, login, other_club, game_master, character, quest_with_stacked_req
    ):
        """Other club's character refused."""
        from accounts.models import Membership, User

        other_user = User.objects.create_user(
            "other@example.com", password="pw", display_name="Other"
        )
        Membership.objects.create(user=other_user, club=other_club)
        owner = Membership.objects.get(user=other_user, club=other_club)
        other_char = character.__class__.objects.create(club=other_club, owner=owner, name="Other")

        c = login(other_user)
        url = reverse("quests:turn_in", args=["club-b", quest_with_stacked_req.pk])
        c.post(url, {"character": other_char.pk}, follow=True)

        # Should fail - different club
        assert QuestCompletion.objects.filter(quest=quest_with_stacked_req).count() == 0

    def test_non_member_cannot_turn_in(self, login, club, parchment):
        """Non-member cannot turn in."""
        from accounts.models import User

        non_member = User.objects.create_user(
            "nonmember@example.com", password="pw", display_name="Non-member"
        )
        # No membership
        c = login(non_member)

        url = reverse("quests:index", args=["club-a"])
        r = c.get(url)

        # Non-member should get 404 (club_member_required returns 404 for non-members)
        assert r.status_code == 404


@pytest.mark.django_db
class TestQuestTurnInAllOrNothing:
    """Tests that turn-in is all or nothing."""

    def test_multiple_requirements_all_or_nothing(
        self, login, player, character, club, parchment, rope
    ):
        """Multiple stacked requirements - all or nothing."""
        quest = Quest.objects.create(club=club, name="Multi", start_date="2024-01-01")
        QuestRequirement.objects.create(quest=quest, item=parchment, quantity=10)
        QuestRequirement.objects.create(quest=quest, item=rope, quantity=20)

        # Has 10 parchment but only 15 rope (need 20)
        lines = [Line(item=parchment, quantity=10), Line(item=rope, quantity=15)]
        record(character, "award", lines, note="Initial")
        c = login(player)

        url = reverse("quests:turn_in", args=["club-a", quest.pk])
        r = c.post(url, {"character": character.pk}, follow=True)

        assert r.status_code == 200
        assert "Missing" in r.content.decode()
        assert QuestCompletion.objects.filter(quest=quest).count() == 0
        # Nothing consumed
        assert available_items(character)[parchment.pk] == 10
        assert available_items(character)[rope.pk] == 15

    def test_multiple_requirements_succeeds_when_all_met(
        self, login, player, character, club, parchment, rope
    ):
        """Multiple stacked requirements - succeeds when all met."""
        quest = Quest.objects.create(club=club, name="Multi", start_date="2024-01-01")
        QuestRequirement.objects.create(quest=quest, item=parchment, quantity=10)
        QuestRequirement.objects.create(quest=quest, item=rope, quantity=20)

        lines = [Line(item=parchment, quantity=10), Line(item=rope, quantity=20)]
        record(character, "award", lines, note="Initial")
        c = login(player)

        url = reverse("quests:turn_in", args=["club-a", quest.pk])
        r = c.post(url, {"character": character.pk}, follow=True)

        assert r.status_code == 200
        assert QuestCompletion.objects.filter(quest=quest).count() == 1
        # Both consumed - quantity 0 means item not in dict
        assert available_items(character).get(parchment.pk, 0) == 0
        assert available_items(character).get(rope.pk, 0) == 0
