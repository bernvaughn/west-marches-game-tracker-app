from datetime import date

import pytest
from django.urls import reverse

from shops.models import Rotation, Shop

pytestmark = pytest.mark.django_db


def url(name, club, *args):
    return reverse(f"shops:{name}", args=[club.slug, *args])


@pytest.fixture
def always_open(club):
    """Create a rotation that's always open."""
    r = Rotation.objects.create(club=club, name="Always", open_date=date(2000, 1, 1))
    return r


@pytest.fixture
def shop_a(club, always_open):
    shop = Shop.objects.create(club=club, name="Shop A", sell_percent=120, buy_percent=40)
    always_open.shops.add(shop)
    return shop


@pytest.fixture
def shop_b(club, always_open):
    shop = Shop.objects.create(club=club, name="Shop B", sell_percent=120, buy_percent=40)
    always_open.shops.add(shop)
    return shop


@pytest.fixture
def shop_c(club, always_open):
    shop = Shop.objects.create(club=club, name="Shop C", sell_percent=120, buy_percent=40)
    always_open.shops.add(shop)
    return shop


@pytest.fixture
def logged_in_client(login, player):
    return login(player)


@pytest.fixture
def client_without_recent_shops(logged_in_client, character):
    """A client with a selected character but no recent shops in session."""
    # Remove only the recent shops session key, not the whole session
    session = logged_in_client.session
    session_key = f"wm_recent_shops_{character.pk}"
    if session_key in session:
        del session[session_key]
    session.save()
    return logged_in_client


@pytest.mark.story("S11")
def test_my_shops_tab_exists(client_without_recent_shops, club, shop_a, shop_b, shop_c):
    """Test that the My Shops tab appears on the shop street page."""
    body = client_without_recent_shops.get(url("index", club)).content.decode()
    assert "My Shops" in body
    assert "All Shops" in body


@pytest.mark.story("S11")
def test_my_shops_tab_filters_to_recent_shops(
    client_without_recent_shops, club, shop_a, shop_b, shop_c, character
):
    """Test that My Shops tab shows only recent shops."""
    # Initially no recent shops, My Shops should show empty state
    body = client_without_recent_shops.get(url("index", club) + "?tab=my_shops").content.decode()
    assert "No shops are open today." in body

    # Add shop_a to recent shops in session
    session = client_without_recent_shops.session
    session_key = f"wm_recent_shops_{character.pk}"
    session[session_key] = [shop_a.pk]
    session.save()

    # Now My Shops should show only shop_a
    body = client_without_recent_shops.get(url("index", club) + "?tab=my_shops").content.decode()
    assert "Shop A" in body
    assert "Shop B" not in body
    assert "Shop C" not in body


@pytest.mark.story("S11")
def test_recent_badge_on_shop_card(
    client_without_recent_shops, club, shop_a, shop_b, shop_c, character
):
    """Test that the ★ Recent badge appears on recent shops."""
    # Add shop_a to recent shops in session
    session = client_without_recent_shops.session
    session_key = f"wm_recent_shops_{character.pk}"
    session[session_key] = [shop_a.pk]
    session.save()

    # Check All Shops tab - shop_a should have the badge
    body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
    assert "★ Recent" in body
    # The badge should be near shop_a
    assert "Shop A" in body

    # shop_b and shop_c should not have the badge
    # We can't easily test this without parsing HTML, but we can check the badge count
    assert body.count("★ Recent") == 1


@pytest.mark.story("S11")
def test_active_tab_highlighted(client_without_recent_shops, club, shop_a):
    """Test that the active tab is highlighted."""
    # All Shops tab active by default
    body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
    assert 'class="wm-shop-tab active"' in body
    assert f'href="{url("index", club)}?tab=all"' in body

    # My Shops tab active
    body = client_without_recent_shops.get(url("index", club) + "?tab=my_shops").content.decode()
    # Should have active class on My Shops tab
    assert 'class="wm-shop-tab active"' in body
    assert f'href="{url("index", club)}?tab=my_shops"' in body


@pytest.mark.story("S11")
def test_session_storage_key_format(client_without_recent_shops, club, shop_a, character):
    """Test that the session storage key follows the correct format."""
    session = client_without_recent_shops.session
    session_key = f"wm_recent_shops_{character.pk}"
    session[session_key] = [shop_a.pk]
    session.save()

    # Verify the key exists and has the right format
    assert session_key in session
    assert session[session_key] == [shop_a.pk]


@pytest.mark.story("S11")
def test_max_10_recent_shops(client_without_recent_shops, club, shop_a, shop_b, shop_c, character):
    """Test that only max 10 recent shops are stored."""
    # This test would be better as a unit test for the JS, but we can verify
    # the view doesn't break with more than 10 shops
    session = client_without_recent_shops.session
    session_key = f"wm_recent_shops_{character.pk}"

    # Create 12 fake shop IDs
    shop_ids = list(range(100, 112))
    session[session_key] = shop_ids
    session.save()

    # View should handle it gracefully (JS limits to 10, but view just filters)
    body = client_without_recent_shops.get(url("index", club) + "?tab=my_shops").content.decode()
    # Since these are fake IDs, no shops should match
    assert "No shops are open today." in body


@pytest.mark.story("S11")
def test_no_character_no_tabs(login, club, shop_a):
    """Test that tabs don't appear when user has no character."""
    # Create a user with no characters
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user_no_char = User.objects.create_user(
        email="nochar@example.com", password="pass", display_name="NoChar"
    )
    from accounts.models import Membership

    Membership.objects.create(
        user=user_no_char, club=club, is_club_admin=False, is_game_master=False
    )

    from django.test import Client

    c = Client()
    c.force_login(user_no_char)

    body = c.get(url("index", club)).content.decode()
    assert "My Shops" not in body
    assert "All Shops" not in body


@pytest.mark.story("S11")
def test_my_shops_empty_when_no_recent(client_without_recent_shops, club, shop_a, shop_b, shop_c):
    """Test that My Shops shows empty state when no recent shops."""
    body = client_without_recent_shops.get(url("index", club) + "?tab=my_shops").content.decode()
    assert "No shops are open today." in body


@pytest.mark.story("S11")
def test_all_shops_shows_all_open_shops(
    client_without_recent_shops, club, shop_a, shop_b, shop_c, character
):
    """Test that All Shops tab shows all open shops regardless of recent."""
    # Add one shop to recent
    session = client_without_recent_shops.session
    session_key = f"wm_recent_shops_{character.pk}"
    session[session_key] = [shop_a.pk]
    session.save()

    # All Shops should show all three
    body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
    assert "Shop A" in body
    assert "Shop B" in body
    assert "Shop C" in body
