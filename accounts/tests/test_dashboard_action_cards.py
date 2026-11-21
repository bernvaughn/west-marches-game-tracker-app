"""Tests for the dashboard action card providers (kept older providers)."""

import pytest

from accounts.dashboard_providers import (
    DowntimeDashboardProvider,
    QuestsDashboardProvider,
    QuickActionsProvider,
)
from accounts.models import Membership
from downtime import services as downtime_services
from downtime.models import DowntimeAction, DowntimeEntry
from ledger.services import Line, record
from player_characters.junk import JunkMark


@pytest.fixture
def provider_quests():
    return QuestsDashboardProvider()


@pytest.fixture
def provider_quick_actions():
    return QuickActionsProvider()


@pytest.fixture
def provider_downtime():
    return DowntimeDashboardProvider()


class MockRequest:
    def __init__(self, club, user):
        self.club = club
        self.user = user


def _membership(player, club):
    return Membership.objects.get(user=player, club=club)


@pytest.fixture
def action(club):
    from datetime import timedelta

    from django.utils import timezone

    return DowntimeAction.objects.create(
        club=club,
        name="Work at a bakery",
        cost=1,
        start_date=timezone.localdate() - timedelta(days=1),
    )


@pytest.fixture
def entries(action):
    return [
        DowntimeEntry.objects.create(action=action, label="Bread", weight=3, coins=10, order=0),
        DowntimeEntry.objects.create(action=action, label="Nothing", weight=1, order=1),
    ]


# ---------------------------------------------------------------------------
# Dashboard view rendering - one card per topic
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_shows_quests_card(club, player, character, quest, item, give, login):
    """Dashboard renders the quests card when a quest is completable."""
    give(character, item, 2)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-quests"' in body
    assert quest.name in body
    assert "Turn in" in body


@pytest.mark.django_db
def test_dashboard_shows_quests_card_empty_fallback(club, player, character, login):
    """Dashboard shows Quest Board fallback when no quests are ready."""
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-quests"' in body
    assert "Quest Board" in body


@pytest.mark.django_db
def test_dashboard_shows_quick_actions_card_with_junk(club, player, character, item, login):
    """Dashboard renders the quick_actions card when the character has junk."""
    record(character, "award", [Line(item=item, quantity=3)], note="t", actor=player)
    JunkMark.objects.create(character=character, item=item, quantity=2)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-quick_actions"' in body
    assert "Sell Junk" in body


@pytest.mark.django_db
def test_dashboard_shows_quick_actions_card_always(club, player, character, login):
    """Quick actions card is always rendered (should_show=True) even when empty.

    This ensures the HTMX partial endpoint returns 200 after the last junk sale,
    allowing the card to refresh properly.
    """
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-quick_actions"' in body
    assert "No quick actions available" in body


@pytest.mark.django_db
def test_dashboard_downtime_card_has_valid_refresh_target(
    club, player, character, action, entries, login
):
    """Downtime card exposes a valid id and refresh url for Close & Refresh.

    Regression: the Close & Refresh button targeted an invalid `:contains()`
    selector and the card had no id, so it never reloaded after a spend.
    """
    downtime_services.award(character, 2, note="test", by=player)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-downtime"' in body, "Downtime card must have a stable id"
    assert f'data-refresh-url="/c/{club.slug}/accounts/dashboard/partial/downtime/"' in body, (
        "Downtime card must expose its refresh url"
    )


@pytest.mark.django_db
def test_dashboard_shows_downtime_card(club, player, character, action, entries, login):
    """Dashboard renders the downtime card when points and an affordable action exist."""
    downtime_services.award(character, 1, note="t", by=player)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-downtime"' in body
    assert action.name in body
    assert "Spend" in body


# ---------------------------------------------------------------------------
# QuestsDashboardProvider
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_quests_provider_attributes(provider_quests):
    """Provider has the expected key, order and template."""
    assert provider_quests.key == "quests"
    assert provider_quests.order == 3
    assert provider_quests.template == "accounts/_dashboard_quests.html"


@pytest.mark.django_db
def test_quests_should_show_true_when_ready(
    provider_quests, player, club, character, quest, item, give
):
    """should_show is True when the character has a completable quest (defaults to True)."""
    give(character, item, 2)  # meet the quest requirement
    request = MockRequest(club, player)
    membership = _membership(player, club)
    # QuestsDashboardProvider doesn't override should_show, so it's always True
    assert provider_quests.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_quests_should_show_true_when_not_ready(provider_quests, player, club, character, quest):
    """should_show is True even when the character lacks the quest requirements."""
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_quests.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_quests_get_context_keys(
    provider_quests, player, club, character, quest, item, give, reward_item
):
    """get_context returns ready_quests and quest_items with fallback."""
    give(character, item, 2)
    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider_quests.get_context(request, club, character, membership)

    assert "ready_quests" in ctx
    assert "quest_items" in ctx
    assert len(ctx["ready_quests"]) == 1
    assert ctx["ready_quests"][0].pk == quest.pk
    # quest_items includes the ready quest with Details/Turn in buttons
    assert len(ctx["quest_items"]) >= 1


# ---------------------------------------------------------------------------
# QuickActionsProvider
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_quick_actions_provider_attributes(provider_quick_actions):
    """Provider has the expected key, order and template."""
    assert provider_quick_actions.key == "quick_actions"
    assert provider_quick_actions.order == 1
    assert provider_quick_actions.template == "accounts/_dashboard_quick_actions.html"


@pytest.mark.django_db
def test_quick_actions_should_show_always_true(provider_quick_actions, player, club, character):
    """should_show is always True so the partial endpoint returns 200 even when empty."""
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_quick_actions.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_quick_actions_get_context_keys(provider_quick_actions, player, club, character, item):
    """get_context returns has_junk, has_potions, junk_count."""
    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider_quick_actions.get_context(request, club, character, membership)

    assert "has_junk" in ctx
    assert "has_potions" in ctx
    assert "junk_count" in ctx
    assert ctx["has_junk"] is False
    assert ctx["has_potions"] is False
    assert ctx["junk_count"] == 0


@pytest.mark.django_db
def test_quick_actions_get_context_with_junk(provider_quick_actions, player, club, character, item):
    """get_context reflects junk when present."""
    record(character, "award", [Line(item=item, quantity=3)], note="t", actor=player)
    JunkMark.objects.create(character=character, item=item, quantity=2)
    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider_quick_actions.get_context(request, club, character, membership)

    assert ctx["has_junk"] is True
    # junk_count is the number of junk rows (item types), not total quantity
    assert ctx["junk_count"] == 1


# ---------------------------------------------------------------------------
# DowntimeDashboardProvider
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_downtime_provider_attributes(provider_downtime):
    """Provider has the expected key, order and template."""
    assert provider_downtime.key == "downtime"
    assert provider_downtime.order == 4
    assert provider_downtime.template == "accounts/_dashboard_downtime.html"


@pytest.mark.django_db
def test_downtime_should_show_true_when_points_and_action(
    provider_downtime, player, club, character, action, entries
):
    """should_show is True when the character has points and an affordable action."""
    downtime_services.award(character, 1, note="test", by=player)
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_downtime.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_downtime_should_show_true_when_no_points_but_actions_exist(
    provider_downtime, player, club, character, action, entries
):
    """should_show is True when live actions exist, even with zero points.

    DowntimeDashboardProvider.should_show only checks for live actions with entries,
    not the character's balance. Balance affects action.affordable in context.
    """
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_downtime.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_downtime_should_show_true_when_action_unaffordable(
    provider_downtime, player, club, character, action, entries
):
    """should_show is True when live actions exist, even if unaffordable.

    Affordability is reflected in the context (action.affordable=False), not in should_show.
    """
    action.cost = 5
    action.save(update_fields=["cost"])
    downtime_services.award(character, 1, note="test", by=player)
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_downtime.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_downtime_get_context_keys(provider_downtime, player, club, character, action, entries):
    """get_context returns actions with cost, reason, affordable and spend_url."""
    downtime_services.award(character, 1, note="test", by=player)
    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider_downtime.get_context(request, club, character, membership)

    assert "downtime_balance" in ctx
    assert "actions" in ctx
    assert ctx["downtime_balance"] == 1
    assert len(ctx["actions"]) == 1
    act = ctx["actions"][0]
    assert act["action"].pk == action.pk
    assert act["cost"] == action.cost
    assert act["affordable"] is True
    assert (
        act["spend_url"] == f"/c/{club.slug}/accounts/dashboard/partial/downtime_spend/{action.pk}/"
    )


# ---------------------------------------------------------------------------
# Dashboard partial endpoint returns 200 for kept providers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_partial_quests_returns_200(club, player, character, login):
    """dashboard_partial for quests returns 200 even when no quests are ready."""
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/partial/quests/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-quests"' in body


@pytest.mark.django_db
def test_dashboard_partial_quick_actions_returns_200(club, player, character, login):
    """dashboard_partial for quick_actions returns 200 even when no junk/potions."""
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/partial/quick_actions/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-quick_actions"' in body


@pytest.mark.django_db
def test_dashboard_partial_downtime_returns_200_when_available(
    club, player, character, action, entries, login
):
    """dashboard_partial for downtime returns 200 when actions are available."""
    downtime_services.award(character, 1, note="test", by=player)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/partial/downtime/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-downtime"' in body


# ---------------------------------------------------------------------------
# Dashboard downtime spend partial view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_downtime_card_link_has_htmx_attributes(club, player, character, action, entries, login):
    """Card link has hx-get, data-app-modal, hx-target and fallback href."""
    downtime_services.award(character, 1, note="test", by=player)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    spend_url = f"/c/{club.slug}/accounts/dashboard/partial/downtime_spend/{action.pk}/"
    play_url = f"/c/{club.slug}/downtime/"
    assert f'hx-get="{spend_url}"' in body
    assert "data-app-modal" in body
    assert 'hx-target="#app-modal .modal-content"' in body
    assert f'href="{play_url}"' in body


@pytest.mark.django_db
def test_downtime_spend_partial_non_htmx_get_redirects(
    club, player, character, action, entries, login
):
    """Non-HTMX GET on spend partial redirects to downtime play page."""
    downtime_services.award(character, 1, note="test", by=player)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/partial/downtime_spend/{action.pk}/")
    assert resp.status_code == 302
    assert resp.url == f"/c/{club.slug}/downtime/"


@pytest.mark.django_db
def test_downtime_spend_partial_htmx_get_returns_confirm_modal(
    club, player, character, action, entries, login
):
    """HTMX GET returns a confirm modal with a form that posts to the spend URL."""
    downtime_services.award(character, 1, note="test", by=player)
    c = login(player)
    spend_url = f"/c/{club.slug}/accounts/dashboard/partial/downtime_spend/{action.pk}/"
    resp = c.get(spend_url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert f'hx-post="{spend_url}"' in body
    assert 'hx-target="#app-modal .modal-content"' in body
    assert "csrfmiddlewaretoken" in body
    assert "Take the job" in body
    assert action.name in body
    assert "Bread" in body and "75.0%" in body
    assert "No reward" not in body
    assert "/result/0/" not in body
    # The GET spends nothing.
    assert downtime_services.balance(character) == 1


@pytest.mark.django_db
def test_downtime_spend_partial_htmx_post_spends_and_returns_result(
    club, player, character, action, entries, login
):
    """HTMX POST spends the point and returns the spin and result modal."""
    downtime_services.award(character, 2, note="test", by=player)
    c = login(player)
    spend_url = f"/c/{club.slug}/accounts/dashboard/partial/downtime_spend/{action.pk}/"
    resp = c.post(spend_url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert downtime_services.balance(character) == 1
    body = resp.content.decode()
    assert "downtime-wheel-data-modal" in body
    assert "downtimeSpent" in resp["HX-Trigger"]
