"""Tests for loot preview on shop surfaces."""

import pytest
from django.urls import reverse

from accounts.models import Membership
from items.tests.factories import _get_or_create_item, add_slot, make_container
from player_characters.models import Character
from shops.models import ShopStock

HX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def container_with_preview(club):
    """Create a container with various preview types."""
    container = make_container(club, name="Diplomat's Pack")
    # Fixed quantity
    parchment = _get_or_create_item(club, "Parchment")
    add_slot(container, [(parchment, 3, 3, 1)], chance_pct=100, unknown=False, position=1)
    # Range quantity
    ink = _get_or_create_item(club, "Ink")
    add_slot(container, [(ink, 1, 4, 1)], chance_pct=100, unknown=False, position=2)
    # Percent chance
    seal = _get_or_create_item(club, "Seal")
    add_slot(container, [(seal, 1, 1, 1)], chance_pct=50, unknown=False, position=3)
    # One of
    letter_a = _get_or_create_item(club, "Letter A")
    letter_b = _get_or_create_item(club, "Letter B")
    add_slot(
        container,
        [(letter_a, 1, 1, 1), (letter_b, 1, 1, 3)],
        chance_pct=100,
        unknown=False,
        position=4,
    )
    return container


@pytest.fixture
def container_unknown(club):
    """Create a container with unknown slot."""
    container = make_container(club, name="Mystery Box")
    secret = _get_or_create_item(club, "Secret Item")
    add_slot(container, [(secret, 1, 1, 1)], chance_pct=100, unknown=True, position=0)
    return container


@pytest.fixture
def shop_stock(club, shop, container_with_preview):
    """Create shop stock with container."""
    return ShopStock.objects.create(shop=shop, item=container_with_preview, quantity=5)


@pytest.fixture
def shop_stock_unknown(club, shop, container_unknown):
    """Create shop stock with unknown container."""
    return ShopStock.objects.create(shop=shop, item=container_unknown, quantity=5)


@pytest.fixture
def seller_with_container(club, other_player, container_with_preview):
    """Create a seller character with container in inventory."""
    from ledger.services import Line, record
    from player_characters.models import JunkMark

    seller_membership = Membership.objects.get(user=other_player, club=club)
    seller = Character.objects.create(club=club, owner=seller_membership, name="Seller")
    seller.shop_open = True
    seller.save()

    # Give seller the container and mark as junk (listed for sale)
    record(seller, "award", [Line(item=container_with_preview, quantity=5)], actor=other_player)
    JunkMark.objects.create(character=seller, item=container_with_preview, quantity=5)

    return seller


@pytest.fixture
def seller_with_unknown_container(club, other_player, container_unknown):
    """Create a seller character with unknown container in inventory."""
    from ledger.services import Line, record
    from player_characters.models import JunkMark

    seller_membership = Membership.objects.get(user=other_player, club=club)
    seller = Character.objects.create(club=club, owner=seller_membership, name="Seller2")
    seller.shop_open = True
    seller.save()

    # Give seller the container and mark as junk (listed for sale)
    record(seller, "award", [Line(item=container_unknown, quantity=5)], actor=other_player)
    JunkMark.objects.create(character=seller, item=container_unknown, quantity=5)

    return seller


@pytest.mark.django_db
class TestShopBuyModalLootPreview:
    """Tests for loot preview in shop buy modal."""

    def test_buy_modal_shows_preview_for_container(
        self, client, club, game_master, rich_character, shop, always_open, shop_stock
    ):
        """Buy modal shows fixed, range, percent, and one-of rows for a container."""
        client.force_login(game_master)
        url = reverse("shops:buy", args=[club.slug, shop.pk, shop_stock.pk])
        response = client.get(url, **HX)
        assert response.status_code == 200
        content = response.content.decode()
        # Should show preview rows
        assert "Parchment" in content
        assert "Ink" in content
        assert "Seal" in content
        assert "50% chance" in content
        assert "One of" in content
        assert "Letter A" in content
        assert "Letter B" in content
        # No Open button
        assert "Open" not in content or "open" not in content.lower()

    def test_buy_modal_masks_unknown_for_player(
        self, client, club, player, character, shop, always_open, shop_stock_unknown
    ):
        """Player sees ??? for unknown items in buy modal."""
        client.force_login(player)
        url = reverse("shops:buy", args=[club.slug, shop.pk, shop_stock_unknown.pk])
        response = client.get(url, **HX)
        assert response.status_code == 200
        content = response.content.decode()
        # Should show ??? not the real name
        assert "???" in content
        assert "Secret Item" not in content

    def test_buy_modal_shows_real_name_for_gm(
        self, client, club, game_master, rich_character, shop, always_open, shop_stock_unknown
    ):
        """GM sees real name for unknown items in buy modal."""
        client.force_login(game_master)
        url = reverse("shops:buy", args=[club.slug, shop.pk, shop_stock_unknown.pk])
        response = client.get(url, **HX)
        assert response.status_code == 200
        content = response.content.decode()
        # Should show real name
        assert "Secret Item" in content

    def test_no_open_button_in_buy_modal(
        self, client, club, player, character, shop, always_open, shop_stock
    ):
        """Buy modal has no Open button or open URL."""
        client.force_login(player)
        url = reverse("shops:buy", args=[club.slug, shop.pk, shop_stock.pk])
        response = client.get(url, **HX)
        content = response.content.decode().lower()
        assert "open" not in content


@pytest.mark.django_db
class TestPlayerShopBuyModalLootPreview:
    """Tests for loot preview in player shop buy modal."""

    def test_player_shop_buy_modal_shows_preview(
        self, client, club, player, character, seller_with_container, container_with_preview
    ):
        """Player shop buy modal shows preview for container."""
        client.force_login(player)
        url = reverse(
            "shops:player_shop_buy",
            args=[club.slug, seller_with_container.pk, container_with_preview.pk],
        )
        response = client.get(url, **HX)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Parchment" in content

    def test_player_shop_buy_masks_unknown(
        self, client, club, player, character, seller_with_unknown_container, container_unknown
    ):
        """Player shop buy modal masks unknown for player."""
        client.force_login(player)
        url = reverse(
            "shops:player_shop_buy",
            args=[club.slug, seller_with_unknown_container.pk, container_unknown.pk],
        )
        response = client.get(url, **HX)
        content = response.content.decode()
        assert "???" in content
        assert "Secret Item" not in content


@pytest.mark.django_db
class TestShopStockTableLootPreview:
    """Tests for loot preview in shop stock table."""

    def test_stock_table_shows_preview_in_details(
        self, client, club, player, character, shop, always_open, shop_stock
    ):
        """Stock table shows preview in collapsed details for container."""
        client.force_login(player)
        url = reverse("shops:stock_fragment", args=[club.slug, shop.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # Stock table should have the item
        assert "Diplomat" in content
        # Preview should be in a details element
        assert "Parchment" in content or "Preview contents" in content


@pytest.mark.django_db
class TestShopLootPreviewLeakSweep:
    """Tests to ensure unknown item names never leak to player HTML on shop surfaces."""

    def test_buy_modal_player_never_sees_sealed_letter(
        self, client, club, player, character, shop, always_open, shop_stock_unknown
    ):
        """Player never sees 'Sealed letter' in buy modal HTML."""
        client.force_login(player)
        url = reverse("shops:buy", args=[club.slug, shop.pk, shop_stock_unknown.pk])
        response = client.get(url, **HX)
        content = response.content.decode()
        assert "Secret Item" not in content

    def test_player_shop_buy_modal_player_never_sees_sealed_letter(
        self, client, club, player, character, seller_with_unknown_container, container_unknown
    ):
        """Player never sees 'Sealed letter' in player shop buy modal HTML."""
        client.force_login(player)
        url = reverse(
            "shops:player_shop_buy",
            args=[club.slug, seller_with_unknown_container.pk, container_unknown.pk],
        )
        response = client.get(url, **HX)
        content = response.content.decode()
        assert "Secret Item" not in content

    def test_stock_table_player_never_sees_sealed_letter(
        self, client, club, player, character, shop, always_open, shop_stock_unknown
    ):
        """Player never sees 'Sealed letter' in stock table HTML."""
        client.force_login(player)
        url = reverse("shops:stock_fragment", args=[club.slug, shop.pk])
        response = client.get(url)
        content = response.content.decode()
        assert "Secret Item" not in content
