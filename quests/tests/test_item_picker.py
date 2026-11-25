"""Tests for the shared item picker widget in quest forms."""

import pytest
from django.urls import reverse

from items.models import Item
from items.widgets import ItemPickerWidget
from quests.forms import RequirementForm, RewardForm
from quests.models import Quest, QuestRequirement, QuestReward

pytestmark = pytest.mark.django_db


def _url(name, club, *args):
    return reverse(f"quests:{name}", args=[club.slug, *args])


@pytest.fixture
def admin_client(login, club_admin):
    return login(club_admin)


@pytest.fixture
def req_item(club):
    """Item for requirements."""
    return Item.objects.create(club=club, name="Wolf Pelt", value_cp=100)


@pytest.fixture
def req_item_2(club):
    """Second item for requirements."""
    return Item.objects.create(club=club, name="Bear Pelt", value_cp=200)


@pytest.fixture
def reward_item(club):
    """Item for rewards."""
    return Item.objects.create(club=club, name="Healing Potion", value_cp=5000)


@pytest.fixture
def stacked_reward_item(club):
    """Stacked item for rewards."""
    return Item.objects.create(
        club=club, name="Arrow", value_cp=2000, is_stacked=True, value_units=20, unit_name="arrow"
    )


@pytest.fixture
def quest(club, req_item, reward_item):
    """Quest with requirements and rewards."""
    q = Quest.objects.create(club=club, name="Test Quest", description="Test")
    QuestRequirement.objects.create(quest=q, item=req_item, quantity=2)
    QuestReward.objects.create(quest=q, item=reward_item, quantity=1)
    QuestReward.objects.create(quest=q, coins=1000)
    return q


@pytest.mark.story("S3")
def test_requirement_form_uses_item_picker_widget(club):
    """RequirementForm's item field uses ItemPickerWidget."""
    form = RequirementForm(club=club)
    assert isinstance(form.fields["item"].widget, ItemPickerWidget)
    assert form.fields["item"].widget.club == club


@pytest.mark.story("S3")
def test_reward_form_uses_item_picker_widget(club):
    """RewardForm's item field uses ItemPickerWidget."""
    form = RewardForm(club=club)
    assert isinstance(form.fields["item"].widget, ItemPickerWidget)
    assert form.fields["item"].widget.club == club


@pytest.mark.story("S3")
def test_requirement_form_queryset_club_scoped(club, other_club, req_item):
    """RequirementForm's item queryset is club-scoped."""
    Item.objects.create(club=other_club, name="Foreign Item", value_cp=100)
    fresh = Item.objects.create(club=club, name="Local Item", value_cp=200)

    form = RequirementForm(club=club)
    qs = form.fields["item"].queryset
    assert list(qs) == [fresh, req_item]


@pytest.mark.story("S3")
def test_saved_requirement_data_identical(admin_client, club, req_item):
    """POSTing to create a quest saves requirement data identically to before."""
    data = {
        "name": "Test Quest",
        "description": "Test",
        "req-TOTAL_FORMS": "1",
        "req-INITIAL_FORMS": "0",
        "req-MIN_NUM_FORMS": "0",
        "req-MAX_NUM_FORMS": "1000",
        "req-0-item": req_item.pk,
        "req-0-quantity": "2",
        "rew-TOTAL_FORMS": "1",
        "rew-INITIAL_FORMS": "0",
        "rew-MIN_NUM_FORMS": "0",
        "rew-MAX_NUM_FORMS": "1000",
        "rew-0-coins_pp": "1",
    }
    response = admin_client.post(_url("create", club), data)
    assert response.status_code == 302

    q = Quest.objects.get(name="Test Quest")
    req = QuestRequirement.objects.get(quest=q)
    assert req.item == req_item
    assert req.quantity == 2


@pytest.mark.story("S3")
def test_saved_reward_data_identical(admin_client, club, reward_item):
    """POSTing to create a quest saves reward data identically to before."""
    data = {
        "name": "Test Quest",
        "description": "Test",
        "req-TOTAL_FORMS": "1",
        "req-INITIAL_FORMS": "0",
        "req-MIN_NUM_FORMS": "0",
        "req-MAX_NUM_FORMS": "1000",
        "req-0-item": reward_item.pk,
        "req-0-quantity": "1",
        "rew-TOTAL_FORMS": "2",
        "rew-INITIAL_FORMS": "0",
        "rew-MIN_NUM_FORMS": "0",
        "rew-MAX_NUM_FORMS": "1000",
        "rew-0-item": reward_item.pk,
        "rew-0-quantity": "3",
        "rew-0-coins_pp": "",
        "rew-1-coins_gp": "5",
    }
    response = admin_client.post(_url("create", club), data)
    assert response.status_code == 302

    q = Quest.objects.get(name="Test Quest")
    rewards = list(q.rewards.order_by("pk"))
    assert rewards[0].item == reward_item
    assert rewards[0].quantity == 3
    assert rewards[0].coins == 0
    assert rewards[1].item is None
    assert rewards[1].quantity == 0
    assert rewards[1].coins == 500


@pytest.mark.story("S3")
def test_quest_create_page_renders_picker_widget(admin_client, club):
    """The quest create page renders the picker widget for requirements and rewards."""
    url = _url("create", club)
    response = admin_client.get(url)
    assert response.status_code == 200

    html = response.content.decode()
    # Widget renders search input and hidden input
    assert 'type="search"' in html
    assert 'placeholder="Search items by name, type, or trait..."' in html
    # Multiple item fields (requirements and rewards)
    assert html.count('name="req-0-item"') >= 1
    assert html.count('name="rew-0-item"') >= 1
    assert 'type="hidden"' in html


@pytest.mark.story("S3")
def test_quest_edit_page_renders_picker_widget(admin_client, club, quest):
    """The quest edit page renders the picker widget for requirements and rewards."""
    url = _url("edit", club, quest.pk)
    response = admin_client.get(url)
    assert response.status_code == 200

    html = response.content.decode()
    assert 'type="search"' in html
    assert 'placeholder="Search items by name, type, or trait..."' in html


@pytest.mark.story("S3")
def test_requirement_form_shows_item_value_on_each_row(admin_client, club, quest):
    """Each requirement row shows the item's value."""
    url = _url("edit", club, quest.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    # The item value should be displayed (100 cp = 1 gp)
    assert "Value:" in html
    assert "1 gp" in html


@pytest.mark.story("S3")
def test_reward_form_shows_item_value_on_each_row(admin_client, club, quest, reward_item):
    """Each reward row shows the item's value."""
    url = _url("edit", club, quest.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    # The reward item value should be displayed (5000 cp = 50 gp)
    assert "Value:" in html
    assert "50 gp" in html


@pytest.mark.story("S3")
def test_reward_total_shown(admin_client, club, quest, reward_item):
    """A reward total (sum of item value x quantity) is shown under the rewards."""
    url = _url("edit", club, quest.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    # Reward total: 5000 cp * 1 = 5000 cp = 50 gp
    assert "Reward total:" in html
    assert "50 gp" in html


@pytest.mark.story("S3")
def test_reward_total_excludes_coins_only_rewards(admin_client, club, reward_item):
    """Coins-only rewards contribute zero to the item-value total."""
    data = {
        "name": "Test Quest",
        "description": "Test",
        "req-TOTAL_FORMS": "1",
        "req-INITIAL_FORMS": "0",
        "req-MIN_NUM_FORMS": "0",
        "req-MAX_NUM_FORMS": "1000",
        "req-0-item": reward_item.pk,
        "req-0-quantity": "1",
        "rew-TOTAL_FORMS": "2",
        "rew-INITIAL_FORMS": "0",
        "rew-MIN_NUM_FORMS": "0",
        "rew-MAX_NUM_FORMS": "1000",
        "rew-0-item": reward_item.pk,
        "rew-0-quantity": "2",
        "rew-0-coins_pp": "",
        "rew-1-coins_gp": "10",
    }
    response = admin_client.post(_url("create", club), data)
    assert response.status_code == 302

    q = Quest.objects.get(name="Test Quest")
    url = _url("edit", club, q.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    # Reward total: 5000 cp * 2 = 10000 cp = 100 gp (coins-only reward contributes 0)
    assert "Reward total:" in html
    assert "100 gp" in html


@pytest.mark.story("S3")
def test_reward_total_with_stacked_item(admin_client, club, stacked_reward_item):
    """Stacked items show correct value in reward total."""
    data = {
        "name": "Test Quest",
        "description": "Test",
        "req-TOTAL_FORMS": "1",
        "req-INITIAL_FORMS": "0",
        "req-MIN_NUM_FORMS": "0",
        "req-MAX_NUM_FORMS": "1000",
        "req-0-item": stacked_reward_item.pk,
        "req-0-quantity": "1",
        "rew-TOTAL_FORMS": "1",
        "rew-INITIAL_FORMS": "0",
        "rew-MIN_NUM_FORMS": "0",
        "rew-MAX_NUM_FORMS": "1000",
        "rew-0-item": stacked_reward_item.pk,
        "rew-0-quantity": "10",
        "rew-0-coins_pp": "",
    }
    response = admin_client.post(_url("create", club), data)
    assert response.status_code == 302

    q = Quest.objects.get(name="Test Quest")
    url = _url("edit", club, q.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    # Stacked item: 2000 cp for 20 arrows = 100 cp per arrow
    # Quantity 10 = 1000 cp = 10 gp
    assert "Reward total:" in html
    assert "10 gp" in html


@pytest.mark.story("S3")
def test_widget_search_url_includes_club_slug(club):
    """The widget's search URL includes the club slug."""
    form = RequirementForm(club=club)
    widget = form.fields["item"].widget
    context = widget.get_context("item", None, {})
    assert f"/c/{club.slug}/items/picker/search/" in context["widget"]["search_url"]


@pytest.mark.story("S3")
def test_requirement_form_validation_unchanged(admin_client, club, req_item):
    """RequirementForm validation works identically to before."""
    data = {
        "name": "Test Quest",
        "description": "Test",
        "req-TOTAL_FORMS": "1",
        "req-INITIAL_FORMS": "0",
        "req-MIN_NUM_FORMS": "0",
        "req-MAX_NUM_FORMS": "1000",
        "req-0-item": req_item.pk,
        "req-0-quantity": "1",
        "rew-TOTAL_FORMS": "1",
        "rew-INITIAL_FORMS": "0",
        "rew-MIN_NUM_FORMS": "0",
        "rew-MAX_NUM_FORMS": "1000",
        "rew-0-coins_gp": "1",
    }

    # Valid submission
    response = admin_client.post(_url("create", club), data)
    assert response.status_code == 302

    # Invalid item (non-existent PK) should fail
    data["req-0-item"] = "99999"
    response = admin_client.post(_url("create", club), data)
    assert response.status_code == 200
    assert "reqs" in response.context
    assert any(f.errors for f in response.context["reqs"].forms)


@pytest.mark.story("S3")
def test_reward_form_validation_unchanged(admin_client, club, reward_item):
    """RewardForm validation works identically to before."""
    data = {
        "name": "Test Quest",
        "description": "Test",
        "req-TOTAL_FORMS": "1",
        "req-INITIAL_FORMS": "0",
        "req-MIN_NUM_FORMS": "0",
        "req-MAX_NUM_FORMS": "1000",
        "req-0-item": reward_item.pk,
        "req-0-quantity": "1",
        "rew-TOTAL_FORMS": "1",
        "rew-INITIAL_FORMS": "0",
        "rew-MIN_NUM_FORMS": "0",
        "rew-MAX_NUM_FORMS": "1000",
        "rew-0-item": reward_item.pk,
        "rew-0-quantity": "2",
        "rew-0-coins_pp": "",
    }

    # Valid submission
    response = admin_client.post(_url("create", club), data)
    assert response.status_code == 302

    # Reward row with quantity but no item and no coins should fail
    data["rew-0-item"] = ""
    data["rew-0-quantity"] = "1"
    data["rew-0-coins_pp"] = ""
    response = admin_client.post(_url("create", club), data)
    assert response.status_code == 200
    assert "rews" in response.context
    assert any(f.errors for f in response.context["rews"].forms)


@pytest.mark.story("S3")
def test_retired_item_not_offered_and_rejected(admin_client, club, req_item, reward_item):
    """Retired items are not offered in the picker and rejected if submitted."""
    retired = Item.objects.create(club=club, name="Old Item", value_cp=1, retired=True)

    # Check retired item not in form choices
    url = _url("create", club)
    response = admin_client.get(url)
    # The widget's no-JS fallback select should not include retired items
    # For the widget, the queryset should exclude retired items
    from quests.forms import RequirementForm

    form = RequirementForm(club=club)
    qs = form.fields["item"].queryset
    assert retired not in qs
    assert req_item in qs

    # Submit with retired item should fail
    data = {
        "name": "Test Quest",
        "description": "Test",
        "req-TOTAL_FORMS": "1",
        "req-INITIAL_FORMS": "0",
        "req-MIN_NUM_FORMS": "0",
        "req-MAX_NUM_FORMS": "1000",
        "req-0-item": retired.pk,
        "req-0-quantity": "1",
        "rew-TOTAL_FORMS": "1",
        "rew-INITIAL_FORMS": "0",
        "rew-MIN_NUM_FORMS": "0",
        "rew-MAX_NUM_FORMS": "1000",
        "rew-0-coins_gp": "1",
    }
    response = admin_client.post(url, data)
    assert response.status_code == 200
    assert not Quest.objects.filter(name="Test Quest").exists()


@pytest.mark.story("S3")
def test_existing_retired_item_kept_on_edit(admin_client, club, quest, req_item, reward_item):
    """Existing retired item is kept in queryset on edit."""
    req_item.retired = True
    req_item.save()

    url = _url("edit", club, quest.pk)
    response = admin_client.get(url)
    assert response.status_code == 200

    # The existing retired item should still be in the queryset for this form
    from quests.forms import RequirementForm

    form = RequirementForm(instance=quest.requirements.first(), club=club)
    qs = form.fields["item"].queryset
    assert req_item in qs

    # Submit with same data should succeed
    req = quest.requirements.get()
    rews = list(quest.rewards.order_by("pk"))
    data = {
        "name": "Renamed",
        "description": "",
        "req-TOTAL_FORMS": "1",
        "req-INITIAL_FORMS": "1",
        "req-0-id": req.pk,
        "req-0-quest": quest.pk,
        "req-0-item": req_item.pk,
        "req-0-quantity": "3",
        "rew-TOTAL_FORMS": len(rews),
        "rew-INITIAL_FORMS": len(rews),
    }
    for i, r in enumerate(rews):
        data[f"rew-{i}-id"] = r.pk
        data[f"rew-{i}-quest"] = quest.pk
        data[f"rew-{i}-item"] = r.item_id or ""
        data[f"rew-{i}-quantity"] = r.quantity
        data[f"rew-{i}-coins_pp"] = "1" if r.coins else ""
    response = admin_client.post(url, data)
    assert response.status_code == 302
    assert QuestRequirement.objects.get(pk=req.pk).quantity == 3
    quest.refresh_from_db()
    assert quest.name == "Renamed"
