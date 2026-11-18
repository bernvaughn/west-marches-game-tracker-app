"""Tests for the Player Shop dashboard provider."""

import pytest

from accounts.dashboard_providers import (
    PlayerShopDashboardProvider,
    get_providers,
    register_provider,
)
from accounts.models import Membership
from ledger.services import Line, record_many
from player_characters.junk import set_junk
from player_characters.models import Character


@pytest.mark.django_db
def test_player_shop_provider_should_show_when_open(player, club, character):
    """Provider should show when character.shop_open is True."""
    provider = PlayerShopDashboardProvider()
    character.shop_open = True
    character.save(update_fields=["shop_open"])

    # Register provider if not already
    for p in get_providers():
        if p.key == "player_shop":
            break
    else:
        register_provider(provider)

    # Create mock request and membership
    class MockRequest:
        pass

    request = MockRequest()
    request.club = club
    request.user = player

    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is True


@pytest.mark.django_db
def test_player_shop_provider_should_not_show_when_closed(player, club, character):
    """Provider should NOT show when character.shop_open is False."""
    provider = PlayerShopDashboardProvider()
    character.shop_open = False
    character.save(update_fields=["shop_open"])

    class MockRequest:
        pass

    request = MockRequest()
    request.club = club
    request.user = player

    membership = Membership.objects.get(user=player, club=club)

    assert provider.should_show(request, club, character, membership) is False


@pytest.mark.django_db
def test_player_shop_provider_get_context_shows_listed_items(player, club, character, item):
    """Provider context includes listed item count."""
    provider = PlayerShopDashboardProvider()
    character.shop_open = True
    character.save(update_fields=["shop_open"])

    # Add item to inventory via ledger first
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=10)],
                note="Test",
                actor=player,
            )
        ]
    )
    # Set junk
    set_junk(character, item, 5, player)

    class MockRequest:
        pass

    request = MockRequest()
    request.club = club
    request.user = player

    membership = Membership.objects.get(user=player, club=club)

    ctx = provider.get_context(request, club, character, membership)

    assert ctx["shop_open"] is True
    assert ctx["listed_count"] == 1  # One item type listed
    assert "manage_url" in ctx


@pytest.mark.django_db
def test_player_shop_provider_get_context_counts_todays_sales(player, club, character, item):
    """Provider context includes today's sales count."""
    provider = PlayerShopDashboardProvider()
    character.shop_open = True
    character.save(update_fields=["shop_open"])

    # Create a buyer character
    membership = Membership.objects.get(user=player, club=club)
    Character.objects.create(
        club=club,
        owner=membership,
        name="Buyer",
        char_class="Fighter",
        level=1,
    )

    # Add item to seller's inventory
    record_many(
        [
            dict(
                character=character,
                kind="award",
                lines=[Line(item=item, quantity=10)],
                note="Test",
                actor=player,
            )
        ]
    )
    set_junk(character, item, 5, player)

    # Record a player_shop sale for today
    record_many(
        [
            dict(
                character=character,
                kind="player_shop",
                lines=[Line(item=item, quantity=-2), Line(coins=200)],
                note="Sold to buyer",
                actor=player,
            )
        ]
    )

    class MockRequest:
        pass

    request = MockRequest()
    request.club = club
    request.user = player

    ctx = provider.get_context(request, club, character, membership)

    assert ctx["recent_sales"] == 1


@pytest.mark.django_db
def test_player_shop_provider_manage_url_points_to_character_detail(player, club, character):
    """Manage URL should point to character detail (where shop toggle lives)."""
    provider = PlayerShopDashboardProvider()
    character.shop_open = True
    character.save(update_fields=["shop_open"])

    class MockRequest:
        pass

    request = MockRequest()
    request.club = club
    request.user = player

    membership = Membership.objects.get(user=player, club=club)

    ctx = provider.get_context(request, club, character, membership)

    expected_url = f"/c/{club.slug}/characters/{character.pk}/"
    assert ctx["manage_url"] == expected_url
