"""Tests for the HeaderDashboardProvider."""

import pytest
from django.urls import reverse

from accounts.dashboard_providers import (
    HeaderDashboardProvider,
    get_providers,
    register_provider,
)
from accounts.models import Membership, Message, User
from ledger.services import Line, record_many
from player_characters.junk import JunkMark
from player_characters.models import Character, Trade


@pytest.fixture
def provider():
    return HeaderDashboardProvider()


@pytest.fixture(autouse=True)
def register_header_provider():
    """Ensure the provider is registered for tests."""
    for p in get_providers():
        if p.key == "header":
            break
    else:
        register_provider(HeaderDashboardProvider())
    yield


class MockRequest:
    def __init__(self, club, user):
        self.club = club
        self.user = user


def _membership(player, club):
    return Membership.objects.get(user=player, club=club)


@pytest.mark.django_db
def test_provider_attributes(provider):
    """Provider has the expected key, order and template."""
    assert provider.key == "header"
    assert provider.order == 0
    assert provider.template == "accounts/_dashboard_header.html"


@pytest.mark.django_db
def test_provider_should_show_is_true(provider, player, club, character):
    """should_show always returns True."""
    request = MockRequest(club, player)
    membership = _membership(player, club)

    assert provider.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_provider_get_context_returns_expected_keys(provider, player, club, character):
    """get_context returns all header context keys."""
    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider.get_context(request, club, character, membership)

    assert "coin_summary" in ctx
    assert "downtime_balance" in ctx
    assert "junk_count" in ctx
    assert "junk_value" in ctx
    assert "open_trades" in ctx
    assert "unread_count" in ctx


@pytest.mark.django_db
def test_provider_context_coins(provider, player, club, character, item):
    """coin_summary.available reflects awarded coins."""
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=1), Line(coins=1000)],
                note="Test",
                actor=player,
            )
        ]
    )

    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider.get_context(request, club, character, membership)

    assert ctx["coin_summary"].available == 1000


@pytest.mark.django_db
def test_provider_context_junk_count_and_value(provider, player, club, character, item):
    """junk_count and junk_value reflect marked junk."""
    item.value_cp = 250
    item.save(update_fields=["value_cp"])

    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=3)],
                note="Test",
                actor=player,
            )
        ]
    )
    JunkMark.objects.create(character=character, item=item, quantity=2)

    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider.get_context(request, club, character, membership)

    # junk_count is the number of junk rows (one per marked item)
    assert ctx["junk_count"] == 1
    assert ctx["junk_value"] == 500


@pytest.mark.django_db
def test_provider_context_open_trades(provider, player, club, character, other_player):
    """open_trades lists trades involving the character's membership."""
    other_char = Character.objects.create(
        club=club, owner=_membership(other_player, club), name="Other"
    )

    trade = Trade.objects.create(
        club=club, sender=character, receiver=other_char, status=Trade.Status.REQUESTED
    )

    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider.get_context(request, club, character, membership)

    assert len(ctx["open_trades"]) == 1
    assert ctx["open_trades"][0]["trade"].pk == trade.pk


@pytest.mark.django_db
def test_provider_context_unread_count(provider, player, club, character):
    """unread_count counts open messages not sent by the membership."""
    admin_user = User.objects.create_user("admin@example.com", password="pw", display_name="Admin")
    admin_mem = Membership.objects.create(user=admin_user, club=club, is_club_admin=True)
    Message.objects.create(club=club, sender=admin_mem, character=character, body="Hello")
    Message.objects.create(club=club, sender=admin_mem, character=character, body="Again")

    request = MockRequest(club, player)
    membership = _membership(player, club)

    ctx = provider.get_context(request, club, character, membership)

    assert ctx["unread_count"] == 2


@pytest.mark.django_db
def test_dashboard_view_renders_header_stats(club, player, character, item, login):
    """Dashboard view renders header stats via the provider."""
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(coins=1000)],
                note="Test",
                actor=player,
            )
        ]
    )

    c = login(player)
    resp = c.get(reverse("accounts:player_dashboard", args=[club.slug]))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert character.name in content
    assert "Downtime Points" in content
    assert "Junk Items" in content
    assert "Junk Value" in content
