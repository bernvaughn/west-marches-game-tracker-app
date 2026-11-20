"""Tests for the new contextual action card providers."""

import pytest

from accounts.dashboard_providers import (
    DowntimeAvailableProvider,
    JunkSummaryProvider,
    QuestsReadyProvider,
    get_providers,
    register_provider,
)
from accounts.models import Membership
from downtime import services as downtime_services
from downtime.models import DowntimeAction, DowntimeEntry
from ledger.services import Line, record
from player_characters.junk import JunkMark


@pytest.fixture
def provider_quests():
    return QuestsReadyProvider()


@pytest.fixture
def provider_junk():
    return JunkSummaryProvider()


@pytest.fixture
def provider_downtime():
    return DowntimeAvailableProvider()


@pytest.fixture(autouse=True)
def register_providers():
    """Ensure the new providers are registered for tests."""
    wanted = {"quests_ready", "junk_summary", "downtime_available"}
    for p in get_providers():
        wanted.discard(p.key)
    for key, cls in (
        ("quests_ready", QuestsReadyProvider),
        ("junk_summary", JunkSummaryProvider),
        ("downtime_available", DowntimeAvailableProvider),
    ):
        if key in wanted:
            register_provider(cls())
    yield


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
# Dashboard view rendering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_shows_quests_ready_card(club, player, character, quest, item, give, login):
    """Dashboard renders the quests_ready card when a quest is completable."""
    give(character, item, 2)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-quests_ready"' in body
    assert quest.name in body
    assert "Turn in" in body


@pytest.mark.django_db
def test_dashboard_hides_quests_ready_card(club, player, character, quest, login):
    """Dashboard hides the quests_ready card when no quest is completable."""
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-quests_ready"' not in body


@pytest.mark.django_db
def test_dashboard_shows_junk_card(club, player, character, item, login):
    """Dashboard renders the junk_summary card when the character has junk."""
    record(character, "award", [Line(item=item, quantity=3)], note="t", actor=player)
    JunkMark.objects.create(character=character, item=item, quantity=2)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-junk_summary"' in body
    assert "Sell junk" in body


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
def test_dashboard_hides_junk_card(club, player, character, login):
    """Dashboard hides the junk_summary card when the character has no junk."""
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-junk_summary"' not in body


@pytest.mark.django_db
def test_dashboard_shows_downtime_card(club, player, character, action, entries, login):
    """Dashboard renders the downtime_available card when points and an affordable action exist."""
    downtime_services.award(character, 1, note="t", by=player)
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-downtime_available"' in body
    assert action.name in body
    assert "Take job" in body


@pytest.mark.django_db
def test_dashboard_hides_downtime_card(club, player, character, login):
    """Dashboard hides the downtime_available card when the character has no points."""
    c = login(player)
    resp = c.get(f"/c/{club.slug}/accounts/dashboard/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'id="dashboard-card-downtime_available"' not in body


# ---------------------------------------------------------------------------
# QuestsReadyProvider
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_quests_provider_attributes(provider_quests):
    """Provider has the expected key, order and template."""
    assert provider_quests.key == "quests_ready"
    assert provider_quests.order == 10
    assert provider_quests.template == "accounts/dashboard_partials/_quests_ready.html"


@pytest.mark.django_db
def test_quests_should_show_true_when_ready(
    provider_quests, player, club, character, quest, item, give
):
    """should_show is True when the character has a completable quest."""
    give(character, item, 2)  # meet the quest requirement
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_quests.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_quests_should_show_false_when_not_ready(provider_quests, player, club, character, quest):
    """should_show is False when the character lacks the quest requirements."""
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_quests.should_show(request, club, character, membership) is False


@pytest.mark.django_db
def test_quests_get_context_keys(
    provider_quests, player, club, character, quest, item, give, reward_item
):
    """get_context returns ready_quests with quest, reward_summary and url."""
    give(character, item, 2)
    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider_quests.get_context(request, club, character, membership)

    assert "ready_quests" in ctx
    assert len(ctx["ready_quests"]) == 1
    entry = ctx["ready_quests"][0]
    assert entry["quest"].pk == quest.pk
    assert entry["url"] == f"/c/{club.slug}/quests/{quest.pk}/"
    assert "10 gp" in entry["reward_summary"]
    assert "Healing potion" in entry["reward_summary"]


# ---------------------------------------------------------------------------
# JunkSummaryProvider
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_junk_provider_attributes(provider_junk):
    """Provider has the expected key, order and template."""
    assert provider_junk.key == "junk_summary"
    assert provider_junk.order == 20
    assert provider_junk.template == "accounts/dashboard_partials/_junk_summary.html"


@pytest.mark.django_db
def test_junk_should_show_true_when_junk(provider_junk, player, club, character, item):
    """should_show is True when the character has marked junk."""
    record(character, "award", [Line(item=item, quantity=3)], note="t", actor=player)
    JunkMark.objects.create(character=character, item=item, quantity=2)
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_junk.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_junk_should_show_false_when_no_junk(provider_junk, player, club, character):
    """should_show is False when the character has no marked junk."""
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_junk.should_show(request, club, character, membership) is False


@pytest.mark.django_db
def test_junk_get_context_keys(provider_junk, player, club, character, item):
    """get_context returns junk_rows, junk_value and sell_url."""
    item.value_cp = 250
    item.save(update_fields=["value_cp"])
    record(character, "award", [Line(item=item, quantity=3)], note="t", actor=player)
    JunkMark.objects.create(character=character, item=item, quantity=2)
    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider_junk.get_context(request, club, character, membership)

    assert "junk_rows" in ctx
    assert "junk_value" in ctx
    assert "sell_url" in ctx
    assert len(ctx["junk_rows"]) == 1
    assert ctx["junk_value"] == "5 gp"
    assert ctx["sell_url"] == f"/c/{club.slug}/accounts/dashboard/partial/quick_action_sell_junk/"


# ---------------------------------------------------------------------------
# DowntimeAvailableProvider
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_downtime_provider_attributes(provider_downtime):
    """Provider has the expected key, order and template."""
    assert provider_downtime.key == "downtime_available"
    assert provider_downtime.order == 30
    assert provider_downtime.template == "accounts/dashboard_partials/_downtime_actions.html"


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
def test_downtime_should_show_false_when_no_points(
    provider_downtime, player, club, character, action, entries
):
    """should_show is False when the character has no downtime points."""
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_downtime.should_show(request, club, character, membership) is False


@pytest.mark.django_db
def test_downtime_should_show_false_when_action_unaffordable(
    provider_downtime, player, club, character, action, entries
):
    """should_show is False when all actions cost more than the balance."""
    action.cost = 5
    action.save(update_fields=["cost"])
    downtime_services.award(character, 1, note="test", by=player)
    request = MockRequest(club, player)
    membership = _membership(player, club)
    assert provider_downtime.should_show(request, club, character, membership) is False


@pytest.mark.django_db
def test_downtime_get_context_keys(provider_downtime, player, club, character, action, entries):
    """get_context returns affordable actions with cost, reward_type and spend_url."""
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
    assert act["reward_type"] == "coins"
    assert (
        act["spend_url"] == f"/c/{club.slug}/accounts/dashboard/partial/downtime_spend/{action.pk}/"
    )


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
