"""Tests for the new database-backed shop favorites feature."""

from datetime import date

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.urls import reverse

from player_characters.models import Character
from shops.models import FavoriteShop, Rotation, Shop

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
    session = logged_in_client.session
    session_key = f"wm_recent_shops_{character.pk}"
    if session_key in session:
        del session[session_key]
    session.save()
    return logged_in_client


@pytest.fixture
def character_with_stall(club, always_open):
    """Create a character with an open stall and listing."""
    from accounts.models import Membership, User
    from items.models import Item
    from ledger.services import record

    # Create a second user for the stall owner
    stall_user = User.objects.create_user(
        email="stallowner@example.com", password="pass", display_name="StallOwner"
    )
    membership = Membership.objects.create(
        user=stall_user, club=club, is_club_admin=False, is_game_master=False
    )
    stall_char = Character.objects.create(
        club=club,
        owner=membership,
        name="Stall Owner",
        shop_open=True,
    )
    # Add some junk to sell
    item = Item.objects.create(club=club, name="Test Item", value_cp=100)
    from player_characters.models import JunkMark

    JunkMark.objects.create(character=stall_char, item=item, quantity=1)
    # Record some inventory
    from ledger.services import Line

    record(character=stall_char, kind="award", lines=[Line(item=item, quantity=1)], note="Test")
    return stall_char


class TestFavoriteShopModel:
    """Tests for the FavoriteShop model."""

    def test_favorite_shop_model_exists(self, character, shop_a):
        """Test that FavoriteShop model can be created."""
        favorite = FavoriteShop.objects.create(character=character, content_object=shop_a)
        assert favorite.character == character
        assert favorite.content_object == shop_a
        assert favorite.created_at is not None

    def test_favorite_shop_unique_constraint(self, character, shop_a):
        """Test that unique constraint prevents duplicate favorites."""
        FavoriteShop.objects.create(character=character, content_object=shop_a)
        with pytest.raises(IntegrityError):
            FavoriteShop.objects.create(character=character, content_object=shop_a)

    def test_favorite_stall_unique_constraint(self, character, character_with_stall):
        """Test that unique constraint works for stalls too."""
        FavoriteShop.objects.create(character=character, content_object=character_with_stall)
        with pytest.raises(IntegrityError):
            FavoriteShop.objects.create(character=character, content_object=character_with_stall)

    def test_favorite_shop_different_characters(self, club, shop_a, character):
        """Test that different characters can favorite the same shop."""
        from accounts.models import Membership, User

        user2 = User.objects.create_user(
            email="user2@example.com", password="pass", display_name="User2"
        )
        membership2 = Membership.objects.create(
            user=user2, club=club, is_club_admin=False, is_game_master=False
        )
        character2 = Character.objects.create(club=club, owner=membership2, name="Character 2")

        shop_ct = ContentType.objects.get_for_model(Shop)
        FavoriteShop.objects.create(character=character, content_type=shop_ct, object_id=shop_a.pk)
        FavoriteShop.objects.create(character=character2, content_type=shop_ct, object_id=shop_a.pk)
        assert FavoriteShop.objects.filter(content_type=shop_ct, object_id=shop_a.pk).count() == 2


class TestFavoriteToggleView:
    """Tests for the favorite toggle endpoint."""

    def test_favorite_toggle_shop_creates_favorite(
        self, client_without_recent_shops, club, shop_a, character
    ):
        """Test that POST to favorite_toggle creates a favorite."""
        response = client_without_recent_shops.post(url("favorite_toggle", club, shop_a.pk))
        assert response.status_code == 200
        shop_ct = ContentType.objects.get_for_model(Shop)
        assert FavoriteShop.objects.filter(
            character=character, content_type=shop_ct, object_id=shop_a.pk
        ).exists()

    def test_favorite_toggle_shop_removes_favorite(
        self, client_without_recent_shops, club, shop_a, character
    ):
        """Test that POST to favorite_toggle removes an existing favorite."""
        # Create favorite first
        shop_ct = ContentType.objects.get_for_model(Shop)
        FavoriteShop.objects.create(character=character, content_type=shop_ct, object_id=shop_a.pk)

        response = client_without_recent_shops.post(url("favorite_toggle", club, shop_a.pk))
        assert response.status_code == 200
        assert not FavoriteShop.objects.filter(
            character=character, content_type=shop_ct, object_id=shop_a.pk
        ).exists()

    def test_favorite_toggle_stall_creates_favorite(
        self, client_without_recent_shops, club, character_with_stall, character
    ):
        """Test that POST to stall_favorite_toggle creates a favorite for a stall."""
        response = client_without_recent_shops.post(
            url("stall_favorite_toggle", club, character_with_stall.pk)
        )
        assert response.status_code == 200
        stall_ct = ContentType.objects.get_for_model(Character)
        assert FavoriteShop.objects.filter(
            character=character, content_type=stall_ct, object_id=character_with_stall.pk
        ).exists()

    def test_favorite_toggle_returns_star_button_partial(
        self, client_without_recent_shops, club, shop_a, character
    ):
        """Test that toggle returns the star button partial."""
        response = client_without_recent_shops.post(url("favorite_toggle", club, shop_a.pk))
        assert response.status_code == 200
        content = response.content.decode()
        assert "★" in content  # Filled star for favorite
        assert "wm-favorite-btn active" in content

    def test_favorite_toggle_returns_hx_trigger(
        self, client_without_recent_shops, club, shop_a, character
    ):
        """Test that toggle returns HX-Trigger for toast notification."""
        response = client_without_recent_shops.post(url("favorite_toggle", club, shop_a.pk))
        assert response.status_code == 200
        assert "HX-Trigger" in response.headers
        assert "toast" in response.headers["HX-Trigger"]

    def test_favorite_toggle_requires_login(self, club, shop_a):
        """Test that favorite toggle requires authentication."""
        from django.test import Client

        c = Client()
        response = c.post(url("favorite_toggle", club, shop_a.pk))
        assert response.status_code in (302, 403)

    def test_favorite_toggle_404_for_invalid_shop(self, client_without_recent_shops, club):
        """Test that toggle returns 404 for invalid shop."""
        response = client_without_recent_shops.post(url("favorite_toggle", club, 99999))
        assert response.status_code == 404


class TestIndexViewFavorites:
    """Tests for the IndexView favorites tab and annotations."""

    def test_favorites_tab_exists(self, client_without_recent_shops, club, shop_a):
        """Test that the Favorites tab appears in the shop tabs."""
        body = client_without_recent_shops.get(url("index", club)).content.decode()
        assert "Favorites" in body

    def test_favorites_tab_shows_only_favorites(
        self, client_without_recent_shops, club, shop_a, shop_b, character
    ):
        """Test that Favorites tab shows only favorited shops."""
        # Add shop_a to favorites
        shop_ct = ContentType.objects.get_for_model(Shop)
        FavoriteShop.objects.create(character=character, content_type=shop_ct, object_id=shop_a.pk)

        # Favorites tab should show only shop_a
        body = client_without_recent_shops.get(
            url("index", club) + "?tab=favorites"
        ).content.decode()
        assert "Shop A" in body
        assert "Shop B" not in body

    def test_favorites_tab_empty_when_no_favorites(
        self, client_without_recent_shops, club, shop_a, shop_b
    ):
        """Test that Favorites tab shows empty state when no favorites."""
        body = client_without_recent_shops.get(
            url("index", club) + "?tab=favorites"
        ).content.decode()
        assert "No shops are open today." in body

    def test_all_shops_tab_shows_favorite_stars(
        self, client_without_recent_shops, club, shop_a, shop_b, character
    ):
        """Test that All Shops tab shows star icons."""
        # Add shop_a to favorites
        shop_ct = ContentType.objects.get_for_model(Shop)
        FavoriteShop.objects.create(character=character, content_type=shop_ct, object_id=shop_a.pk)

        body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
        # Should have star buttons
        assert "wm-favorite-btn" in body
        assert body.count("wm-favorite-btn") >= 2  # At least for shop_a and shop_b

    def test_active_tab_favorites_highlighted(
        self, client_without_recent_shops, club, shop_a, character
    ):
        """Test that Favorites tab is highlighted when active."""
        shop_ct = ContentType.objects.get_for_model(Shop)
        FavoriteShop.objects.create(character=character, content_type=shop_ct, object_id=shop_a.pk)

        body = client_without_recent_shops.get(
            url("index", club) + "?tab=favorites"
        ).content.decode()
        # Favorites tab should have active class
        assert 'class="wm-shop-tab active"' in body
        assert f'href="{url("index", club)}?tab=favorites"' in body

    def test_favorite_persists_across_requests(
        self, client_without_recent_shops, club, shop_a, character
    ):
        """Test that favorites persist (database-backed)."""
        # Add favorite via POST
        client_without_recent_shops.post(url("favorite_toggle", club, shop_a.pk))

        # Verify it exists in database
        shop_ct = ContentType.objects.get_for_model(Shop)
        assert FavoriteShop.objects.filter(
            character=character, content_type=shop_ct, object_id=shop_a.pk
        ).exists()

        # New request should still show it as favorite
        body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
        assert "wm-favorite-btn active" in body

    def test_favorite_works_for_stall(
        self, client_without_recent_shops, club, character_with_stall, character
    ):
        """Test that favorites work for player stalls."""
        # Add stall to favorites
        stall_ct = ContentType.objects.get_for_model(Character)
        FavoriteShop.objects.create(
            character=character, content_type=stall_ct, object_id=character_with_stall.pk
        )

        # Favorites tab should show the stall
        body = client_without_recent_shops.get(
            url("index", club) + "?tab=favorites"
        ).content.decode()
        assert "Stall Owner's stall" in body

    def test_all_shops_shows_stall_favorite_star(
        self, client_without_recent_shops, club, character_with_stall, character
    ):
        """Test that All Shops tab shows favorite star for stalls."""
        stall_ct = ContentType.objects.get_for_model(Character)
        FavoriteShop.objects.create(
            character=character, content_type=stall_ct, object_id=character_with_stall.pk
        )

        body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
        assert "wm-favorite-btn active" in body


class TestFavoriteTabOrder:
    """Tests for tab ordering."""

    def test_tab_order_all_my_shops_favorites(self, client_without_recent_shops, club, shop_a):
        """Test that tab order is All Shops, My Shops, Favorites."""
        body = client_without_recent_shops.get(url("index", club)).content.decode()
        # Find positions of tabs
        all_pos = body.find("All Shops")
        my_shops_pos = body.find("My Shops")
        favorites_pos = body.find("Favorites")

        assert all_pos != -1
        assert my_shops_pos != -1
        assert favorites_pos != -1
        assert all_pos < my_shops_pos < favorites_pos


class TestFavoriteStarButtonAccessibility:
    """Tests for accessibility of the star button."""

    def test_star_button_has_aria_label(self, client_without_recent_shops, club, shop_a, character):
        """Test that star button has aria-label."""
        shop_ct = ContentType.objects.get_for_model(Shop)
        FavoriteShop.objects.create(character=character, content_type=shop_ct, object_id=shop_a.pk)

        body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
        assert 'aria-label="Remove from favorites"' in body

    def test_star_button_has_aria_pressed(
        self, client_without_recent_shops, club, shop_a, character
    ):
        """Test that star button has aria-pressed."""
        shop_ct = ContentType.objects.get_for_model(Shop)
        FavoriteShop.objects.create(character=character, content_type=shop_ct, object_id=shop_a.pk)

        body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
        assert 'aria-pressed="true"' in body

    def test_star_button_hollow_when_not_favorite(self, client_without_recent_shops, club, shop_a):
        """Test that star is hollow (☆) when not a favorite."""
        body = client_without_recent_shops.get(url("index", club) + "?tab=all").content.decode()
        assert "☆" in body  # Hollow star
