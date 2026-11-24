import pytest
from django.urls import reverse

from quests.models import Quest, QuestCompletion, QuestRequirement, QuestReward


@pytest.mark.django_db
def test_quest_admin_changelist_and_change(site_admin, login, club):
    client = login(site_admin)
    url = reverse("admin:quests_quest_changelist")
    response = client.get(url)
    assert response.status_code == 200

    quest = Quest.objects.create(club=club, name="Test Quest")
    url = reverse("admin:quests_quest_change", args=[quest.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_quest_requirement_admin_changelist_and_change(site_admin, login, club, item):
    client = login(site_admin)
    url = reverse("admin:quests_questrequirement_changelist")
    response = client.get(url)
    assert response.status_code == 200

    quest = Quest.objects.create(club=club, name="Test Quest")
    req = QuestRequirement.objects.create(quest=quest, item=item, quantity=1)
    url = reverse("admin:quests_questrequirement_change", args=[req.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_quest_reward_admin_changelist_and_change(site_admin, login, club, item):
    client = login(site_admin)
    url = reverse("admin:quests_questreward_changelist")
    response = client.get(url)
    assert response.status_code == 200

    quest = Quest.objects.create(club=club, name="Test Quest")
    reward = QuestReward.objects.create(quest=quest, item=item, quantity=1, coins=100)
    url = reverse("admin:quests_questreward_change", args=[reward.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_quest_completion_admin_changelist_and_change(site_admin, login, club, character, item):
    client = login(site_admin)
    url = reverse("admin:quests_questcompletion_changelist")
    response = client.get(url)
    assert response.status_code == 200

    quest = Quest.objects.create(club=club, name="Test Quest")
    completion = QuestCompletion.objects.create(quest=quest, character=character, date="2024-01-15")
    url = reverse("admin:quests_questcompletion_change", args=[completion.pk])
    response = client.get(url)
    assert response.status_code == 200
