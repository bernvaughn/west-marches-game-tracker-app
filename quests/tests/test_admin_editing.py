"""Tests for quests admin editing (autocomplete, inlines, readonly stamps)."""

import pytest
from django.core.checks import run_checks
from django.urls import reverse

from quests.models import Quest, QuestCompletion, QuestRequirement, QuestReward

pytestmark = pytest.mark.django_db


def _get_admin_form_field(admin_class, field_name):
    """Helper to get a form field from an admin class."""
    from django.contrib import admin

    model_admin = admin.site._registry[admin_class.model]
    form = model_admin.get_form(None)()
    return form.fields[field_name]


class TestQuestAdminEditing:
    """QuestAdmin: autocomplete club, inlines with autocomplete item."""

    def test_changelist(self, site_admin, login):
        client = login(site_admin)
        url = reverse("admin:quests_quest_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_add_form(self, site_admin, login, club):
        client = login(site_admin)
        url = reverse("admin:quests_quest_add")
        response = client.get(url)
        assert response.status_code == 200
        # Club widget should be autocomplete
        assert "admin-autocomplete" in response.content.decode()

    def test_change_form(self, site_admin, login, club, item):
        client = login(site_admin)
        quest = Quest.objects.create(club=club, name="Test Quest")
        # Create inline objects so they appear in the change form (extra=0)
        QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
        QuestReward.objects.create(quest=quest, item=item, quantity=1, coins=100)
        url = reverse("admin:quests_quest_change", args=[quest.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # Club widget should be autocomplete
        assert "admin-autocomplete" in content
        # Inline item widgets should be autocomplete
        assert 'id="id_requirements-0-item"' in content
        assert 'id="id_rewards-0-item"' in content

    def test_autocomplete_fields_configured(self):
        """QuestAdmin has autocomplete_fields = ['club']."""
        from django.contrib import admin

        quest_admin = admin.site._registry[Quest]
        assert "club" in quest_admin.autocomplete_fields


class TestQuestRequirementAdminEditing:
    """QuestRequirementAdmin: autocomplete quest and item."""

    def test_changelist(self, site_admin, login, club, item):
        client = login(site_admin)
        Quest.objects.create(club=club, name="Test Quest")
        url = reverse("admin:quests_questrequirement_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_add_form(self, site_admin, login, club, item):
        client = login(site_admin)
        Quest.objects.create(club=club, name="Test Quest")
        url = reverse("admin:quests_questrequirement_add")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_change_form(self, site_admin, login, club, item):
        client = login(site_admin)
        quest = Quest.objects.create(club=club, name="Test Quest")
        req = QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
        url = reverse("admin:quests_questrequirement_change", args=[req.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_post_edit_saves(self, site_admin, login, club, item):
        """POST a valid change and assert it saves."""
        client = login(site_admin)
        quest = Quest.objects.create(club=club, name="Test Quest")
        req = QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
        url = reverse("admin:quests_questrequirement_change", args=[req.pk])
        data = {
            "quest": quest.pk,
            "item": item.pk,
            "quantity": 5,
        }
        response = client.post(url, data)
        assert response.status_code == 302
        req.refresh_from_db()
        assert req.quantity == 5

    def test_autocomplete_fields_configured(self):
        from django.contrib import admin

        req_admin = admin.site._registry[QuestRequirement]
        assert "quest" in req_admin.autocomplete_fields
        assert "item" in req_admin.autocomplete_fields


class TestQuestRewardAdminEditing:
    """QuestRewardAdmin: autocomplete quest and item."""

    def test_changelist(self, site_admin, login, club, item):
        client = login(site_admin)
        Quest.objects.create(club=club, name="Test Quest")
        url = reverse("admin:quests_questreward_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_add_form(self, site_admin, login, club, item):
        client = login(site_admin)
        Quest.objects.create(club=club, name="Test Quest")
        url = reverse("admin:quests_questreward_add")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_change_form(self, site_admin, login, club, item):
        client = login(site_admin)
        quest = Quest.objects.create(club=club, name="Test Quest")
        reward = QuestReward.objects.create(quest=quest, item=item, quantity=1, coins=100)
        url = reverse("admin:quests_questreward_change", args=[reward.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_autocomplete_fields_configured(self):
        from django.contrib import admin

        reward_admin = admin.site._registry[QuestReward]
        assert "quest" in reward_admin.autocomplete_fields
        assert "item" in reward_admin.autocomplete_fields


class TestQuestCompletionAdminEditing:
    """QuestCompletionAdmin: autocomplete quest and character; created is readonly."""

    def test_changelist(self, site_admin, login, club, character):
        client = login(site_admin)
        Quest.objects.create(club=club, name="Test Quest")
        url = reverse("admin:quests_questcompletion_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_add_form(self, site_admin, login, club, character):
        client = login(site_admin)
        Quest.objects.create(club=club, name="Test Quest")
        url = reverse("admin:quests_questcompletion_add")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_change_form(self, site_admin, login, club, character):
        client = login(site_admin)
        quest = Quest.objects.create(club=club, name="Test Quest")
        completion = QuestCompletion.objects.create(
            quest=quest, character=character, date="2024-01-15"
        )
        url = reverse("admin:quests_questcompletion_change", args=[completion.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content
        # created field should be readonly (not editable)
        assert "readonly" in content.lower()

    def test_created_is_readonly(self):
        """QuestCompletion.created is auto_now_add, so readonly in admin."""
        from django.contrib import admin

        completion_admin = admin.site._registry[QuestCompletion]
        assert "created" in completion_admin.readonly_fields

    def test_autocomplete_fields_configured(self):
        from django.contrib import admin

        completion_admin = admin.site._registry[QuestCompletion]
        assert "quest" in completion_admin.autocomplete_fields
        assert "character" in completion_admin.autocomplete_fields


class TestQuestInlines:
    """RequirementInline and RewardInline use autocomplete for item."""

    def test_requirement_inline_item_autocomplete(self):
        from django.contrib import admin

        from quests.admin import RequirementInline

        inline = RequirementInline(QuestRequirement, admin.site)
        assert "item" in inline.autocomplete_fields

    def test_reward_inline_item_autocomplete(self):
        from django.contrib import admin

        from quests.admin import RewardInline

        inline = RewardInline(QuestReward, admin.site)
        assert "item" in inline.autocomplete_fields


class TestAdminChecks:
    """django.core.checks.run_checks() reports no admin errors."""

    def test_no_admin_errors(self):
        errors = [e for e in run_checks() if e.id.startswith("admin.")]
        assert errors == [], f"Admin errors: {errors}"
