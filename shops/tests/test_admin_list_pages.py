"""Tests for shops admin list pages."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from shops.models import FavoriteShop, Rotation, Shop, ShopStock

pytestmark = pytest.mark.django_db


def test_shop_admin_changelist_and_change(site_admin, login, club):
    client = login(site_admin)

    # Changelist
    url = reverse("admin:shops_shop_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance
    shop = Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")

    # Change form
    url = reverse("admin:shops_shop_change", args=[shop.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_shopstock_admin_changelist_and_change(site_admin, login, club, item):
    client = login(site_admin)

    # Changelist
    url = reverse("admin:shops_shopstock_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance (needs shop + item)
    shop = Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
    stock = ShopStock.objects.create(shop=shop, item=item, bundle_units=1, quantity=10)

    # Change form
    url = reverse("admin:shops_shopstock_change", args=[stock.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_rotation_admin_changelist_and_change(site_admin, login, club):
    client = login(site_admin)

    # Changelist
    url = reverse("admin:shops_rotation_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance
    from datetime import date

    rotation = Rotation.objects.create(club=club, name="Test Rotation", open_date=date(2024, 1, 1))

    # Change form
    url = reverse("admin:shops_rotation_change", args=[rotation.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_favoriteshop_admin_changelist_and_change(site_admin, login, club, character):
    client = login(site_admin)

    # Changelist
    url = reverse("admin:shops_favoriteshop_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance (needs character + content_type + object_id for GenericForeignKey)
    shop = Shop.objects.create(club=club, name="Test Shop", keeper_name="Keeper")
    content_type = ContentType.objects.get_for_model(Shop)
    favorite = FavoriteShop.objects.create(
        character=character,
        content_type=content_type,
        object_id=shop.pk,
    )

    # Change form
    url = reverse("admin:shops_favoriteshop_change", args=[favorite.pk])
    response = client.get(url)
    assert response.status_code == 200
