"""Tests for shops admin editing (autocomplete, inlines, readonly stamps).

Notes:
- created_at on FavoriteShop is auto_now_add, never hand-corrected.
- content_type on FavoriteShop stays a plain select (ContentType has no admin).
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.checks import run_checks
from django.urls import reverse

from shops.models import FavoriteShop, Rotation, Shop, ShopStock

pytestmark = pytest.mark.django_db


class TestShopAdminEditing:
    """ShopAdmin: autocomplete club, ShopStockInline with autocomplete item."""

    def test_changelist(self, site_admin, login):
        client = login(site_admin)
        url = reverse("admin:shops_shop_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_add_form(self, site_admin, login, club):
        client = login(site_admin)
        url = reverse("admin:shops_shop_add")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_change_form(self, site_admin, login, club, item):
        client = login(site_admin)
        shop = Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
        # Create inline object so it appears in the change form (extra=0)
        ShopStock.objects.create(shop=shop, item=item, bundle_units=1, quantity=10)
        url = reverse("admin:shops_shop_change", args=[shop.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content
        # Stock inline should be present
        assert "Shop stock" in content
        assert 'id="id_stock-0-item"' in content

    def test_post_edit_saves(self, site_admin, login, club, item):
        """POST a valid change with inline management form and assert it saves."""
        client = login(site_admin)
        shop = Shop.objects.create(club=club, name="Test Shop", keeper_name="Old Keeper")
        # Create existing stock for the management form
        ShopStock.objects.create(shop=shop, item=item, bundle_units=1, quantity=10)

        url = reverse("admin:shops_shop_change", args=[shop.pk])
        data = {
            "club": club.pk,
            "name": "Test Shop",
            "keeper_name": "New Keeper",
            "keeper_description": "",
            "sell_percent": "100",
            "buy_percent": "50",
            "color": "parchment",
            "silhouette": "hooded_trader",
            "building": "general_store",
            "street_position": "0",
            "symbol": "",
            # Inline management form
            "stock-TOTAL_FORMS": "1",
            "stock-INITIAL_FORMS": "1",
            "stock-MIN_NUM_FORMS": "0",
            "stock-MAX_NUM_FORMS": "1000",
            "stock-0-shop": shop.pk,
            "stock-0-item": item.pk,
            "stock-0-bundle_units": "1",
            "stock-0-quantity": "20",
            "stock-0-sell_percent": "",
            "stock-0-buy_percent": "",
            "stock-0-id": ShopStock.objects.get(shop=shop, item=item).pk,
        }
        response = client.post(url, data)
        assert response.status_code == 302
        shop.refresh_from_db()
        assert shop.keeper_name == "New Keeper"

    def test_autocomplete_fields_configured(self):
        from django.contrib import admin

        shop_admin = admin.site._registry[Shop]
        assert "club" in shop_admin.autocomplete_fields


class TestShopStockAdminEditing:
    """ShopStockAdmin: autocomplete shop and item."""

    def test_changelist(self, site_admin, login, club, item):
        client = login(site_admin)
        Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
        url = reverse("admin:shops_shopstock_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_add_form(self, site_admin, login, club, item):
        client = login(site_admin)
        Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
        url = reverse("admin:shops_shopstock_add")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_change_form(self, site_admin, login, club, item):
        client = login(site_admin)
        shop = Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
        stock = ShopStock.objects.create(shop=shop, item=item, bundle_units=1, quantity=10)
        url = reverse("admin:shops_shopstock_change", args=[stock.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_autocomplete_fields_configured(self):
        from django.contrib import admin

        stock_admin = admin.site._registry[ShopStock]
        assert "shop" in stock_admin.autocomplete_fields
        assert "item" in stock_admin.autocomplete_fields


class TestShopStockInline:
    """ShopStockInline: extra=0, show_change_link=True, autocomplete item."""

    def test_inline_configured(self):
        from django.contrib import admin

        from shops.admin import ShopStockInline

        inline = ShopStockInline(ShopStock, admin.site)
        assert inline.extra == 0
        assert inline.show_change_link is True
        assert "item" in inline.autocomplete_fields


class TestRotationAdminEditing:
    """RotationAdmin: autocomplete club and shops (M2M)."""

    def test_changelist(self, site_admin, login, club):
        client = login(site_admin)
        url = reverse("admin:shops_rotation_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_add_form(self, site_admin, login, club):
        client = login(site_admin)
        url = reverse("admin:shops_rotation_add")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_change_form(self, site_admin, login, club):
        from datetime import date

        client = login(site_admin)
        rotation = Rotation.objects.create(
            club=club, name="Test Rotation", open_date=date(2024, 1, 1)
        )
        url = reverse("admin:shops_rotation_change", args=[rotation.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "admin-autocomplete" in content

    def test_autocomplete_fields_configured(self):
        from django.contrib import admin

        rotation_admin = admin.site._registry[Rotation]
        assert "club" in rotation_admin.autocomplete_fields
        assert "shops" in rotation_admin.autocomplete_fields


class TestFavoriteShopAdminEditing:
    """FavoriteShopAdmin: autocomplete character; content_type stays a
    select; created_at readonly."""

    def test_changelist(self, site_admin, login, club, character):
        client = login(site_admin)
        shop = Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
        content_type = ContentType.objects.get_for_model(Shop)
        FavoriteShop.objects.create(
            character=character, content_type=content_type, object_id=shop.pk
        )
        url = reverse("admin:shops_favoriteshop_changelist")
        response = client.get(url)
        assert response.status_code == 200

    def test_add_form(self, site_admin, login, club, character):
        client = login(site_admin)
        Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
        url = reverse("admin:shops_favoriteshop_add")
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # character widget should be autocomplete
        assert "admin-autocomplete" in content
        # content_type should be a plain select
        assert 'id="id_content_type"' in content
        assert "<select" in content

    def test_change_form(self, site_admin, login, club, character):
        client = login(site_admin)
        shop = Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
        content_type = ContentType.objects.get_for_model(Shop)
        favorite = FavoriteShop.objects.create(
            character=character, content_type=content_type, object_id=shop.pk
        )
        url = reverse("admin:shops_favoriteshop_change", args=[favorite.pk])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # character widget should be autocomplete
        assert "admin-autocomplete" in content
        # content_type should be a plain select
        assert 'id="id_content_type"' in content
        assert "<select" in content
        # created_at should be readonly
        assert "readonly" in content.lower()

    def test_created_at_is_readonly(self):
        """FavoriteShop.created_at is auto_now_add, so readonly in admin."""
        from django.contrib import admin

        favorite_admin = admin.site._registry[FavoriteShop]
        assert "created_at" in favorite_admin.readonly_fields

    def test_autocomplete_fields_configured(self):
        from django.contrib import admin

        favorite_admin = admin.site._registry[FavoriteShop]
        assert "character" in favorite_admin.autocomplete_fields
        # content_type should NOT be in autocomplete_fields (plain select)
        assert "content_type" not in favorite_admin.autocomplete_fields

    def test_get_queryset_prefetches_content_object(self):
        """FavoriteShopAdmin.get_queryset prefetches content_object to avoid N+1."""
        from django.contrib import admin

        from shops.admin import FavoriteShopAdmin

        favorite_admin = FavoriteShopAdmin(FavoriteShop, admin.site)
        # The get_queryset method should exist and use prefetch_related
        import inspect

        source = inspect.getsource(favorite_admin.get_queryset)
        assert "prefetch_related" in source
        assert "content_object" in source


class TestAdminChecks:
    """django.core.checks.run_checks() reports no admin errors."""

    def test_no_admin_errors(self):
        errors = [e for e in run_checks() if e.id.startswith("admin.")]
        assert errors == [], f"Admin errors: {errors}"
