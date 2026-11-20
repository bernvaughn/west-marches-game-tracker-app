"""Schema tests for ShopStock.bundle_units and the new unique key (U125)."""

import pytest
from django.db import IntegrityError, transaction

from items.tests.factories import make_rope
from shops.models import ShopStock


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_bundle_units_defaults_to_one(club, shop):
    stock = ShopStock.objects.create(shop=shop, item=make_rope(club))
    assert stock.bundle_units == 1


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_two_bundle_lines_same_item_different_sizes_allowed(club, shop):
    rope = make_rope(club)
    ShopStock.objects.create(shop=shop, item=rope, bundle_units=5, quantity=10)
    ShopStock.objects.create(shop=shop, item=rope, bundle_units=100, quantity=1)
    assert shop.stock.count() == 2


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_duplicate_shop_item_bundle_units_raises(club, shop):
    rope = make_rope(club)
    ShopStock.objects.create(shop=shop, item=rope, bundle_units=5, quantity=10)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ShopStock.objects.create(shop=shop, item=rope, bundle_units=5, quantity=3)


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_bundle_units_zero_raises(club, shop):
    rope = make_rope(club)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ShopStock.objects.create(shop=shop, item=rope, bundle_units=0)


@pytest.mark.story("U125")
@pytest.mark.django_db
def test_different_shops_can_share_a_bundle_size(other_club, shop, other_shop):
    rope = make_rope(shop.club)
    ShopStock.objects.create(shop=shop, item=rope, bundle_units=5, quantity=10)
    ShopStock.objects.create(shop=other_shop, item=rope, bundle_units=5, quantity=3)
    assert ShopStock.objects.count() == 2
