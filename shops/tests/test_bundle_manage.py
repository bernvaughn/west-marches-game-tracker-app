"""Manage tests for shop bundle lines (U125, U126, U127)."""

import pytest
from django.urls import reverse

from items.tests.factories import make_arrows, make_parchment, make_rope, make_stacked
from shops.models import ShopStock
from shops.services import sell_price

pytestmark = [pytest.mark.django_db, pytest.mark.story("U125")]


def u(name, club, *ids):
    keys = {
        "manage_list": [],
        "manage_create": [],
        "manage_edit": ["shop_id"],
        "stock_add": ["shop_id"],
        "stock_edit": ["shop_id", "stock_id"],
        "stock_remove": ["shop_id", "stock_id"],
    }[name]
    kwargs = {"club_slug": club.slug, **dict(zip(keys, ids, strict=True))}
    return reverse(f"shops:{name}", kwargs=kwargs)


@pytest.fixture
def admin_client(club_admin, login):
    return login(club_admin)


@pytest.fixture
def arrows(club):
    return make_arrows(club)


@pytest.fixture
def rope(club):
    return make_rope(club)


@pytest.fixture
def parchment(club):
    return make_parchment(club)


def test_add_two_bundle_lines_same_item_different_sizes(admin_client, club, shop, arrows):
    """Admin can add two bundle lines of one item with separate stock."""
    # Add bundle of 5 arrows
    r = admin_client.post(
        u("stock_add", club, shop.pk),
        {"item": arrows.pk, "bundle_units": "5", "quantity": "10"},
    )
    assert r.status_code == 302
    stock5 = ShopStock.objects.get(shop=shop, item=arrows, bundle_units=5)
    assert stock5.quantity == 10

    # Add bundle of 100 arrows
    r = admin_client.post(
        u("stock_add", club, shop.pk),
        {"item": arrows.pk, "bundle_units": "100", "quantity": "2"},
    )
    assert r.status_code == 302
    stock100 = ShopStock.objects.get(shop=shop, item=arrows, bundle_units=100)
    assert stock100.quantity == 2

    # Both lines exist
    assert shop.stock.count() == 2


def test_same_bundle_size_twice_refused(admin_client, club, shop, arrows):
    """Adding same bundle size twice is refused with message."""
    admin_client.post(
        u("stock_add", club, shop.pk),
        {"item": arrows.pk, "bundle_units": "5", "quantity": "10"},
    )
    r = admin_client.post(
        u("stock_add", club, shop.pk),
        {"item": arrows.pk, "bundle_units": "5", "quantity": "3"},
    )
    assert r.status_code == 200
    assert "This shop already has a bundle of 5 for this item." in r.content.decode()


def test_non_stacked_with_bundle_size_gt_1_refused(admin_client, club, shop):
    """Non-stacked item with bundle size > 1 is refused."""
    normal = ShopStock._meta.get_field("item").related_model.objects.create(
        club=club, name="Torch", value_cp=10
    )
    r = admin_client.post(
        u("stock_add", club, shop.pk),
        {"item": normal.pk, "bundle_units": "5", "quantity": "10"},
    )
    assert r.status_code == 200
    assert "Non-stacked items must have bundle size 1." in r.content.decode()


def test_non_stacked_item_not_offered_again(admin_client, club, shop):
    """Non-stacked item with existing line is not offered in add form."""
    normal = ShopStock._meta.get_field("item").related_model.objects.create(
        club=club, name="Torch", value_cp=10
    )
    ShopStock.objects.create(shop=shop, item=normal, quantity=5)
    # GET the add form
    r = admin_client.get(u("stock_add", club, shop.pk))
    assert r.status_code == 200
    # The item should not be in the queryset
    form = r.context["form"]
    assert normal not in form.fields["item"].queryset


def test_edit_line_to_clashing_size_refused(admin_client, club, shop, arrows):
    """Editing a line to a bundle size that already exists is refused."""
    stock5 = ShopStock.objects.create(shop=shop, item=arrows, bundle_units=5, quantity=10)
    ShopStock.objects.create(shop=shop, item=arrows, bundle_units=100, quantity=2)
    r = admin_client.post(
        u("stock_edit", club, shop.pk, stock5.pk),
        {"bundle_units": "100", "quantity": "10"},
    )
    assert r.status_code == 200
    assert "This shop already has a bundle of 100 for this item." in r.content.decode()


def test_zero_stock_and_unlimited_both_save(admin_client, club, shop, arrows):
    """0 stock and unlimited (blank) both save."""
    # Zero stock
    r = admin_client.post(
        u("stock_add", club, shop.pk),
        {"item": arrows.pk, "bundle_units": "5", "quantity": "0"},
    )
    assert r.status_code == 302
    stock = ShopStock.objects.get(shop=shop, item=arrows, bundle_units=5)
    assert stock.quantity == 0

    # Unlimited (blank quantity)
    r = admin_client.post(
        u("stock_add", club, shop.pk),
        {"item": arrows.pk, "bundle_units": "10", "quantity": ""},
    )
    assert r.status_code == 302
    stock = ShopStock.objects.get(shop=shop, item=arrows, bundle_units=10)
    assert stock.quantity is None


def test_default_bundle_price_rounds_up(admin_client, club, shop, arrows):
    """Default bundle price uses ceil rounding."""
    # Arrows: 100 cp per 20 arrows. Bundle of 5 at 100% = ceil(100*5*100/(100*20)) = ceil(25) = 25
    stock = ShopStock.objects.create(shop=shop, item=arrows, bundle_units=5, quantity=10)
    assert sell_price(stock) == 25

    # Exact value: bundle of 3 at 100% = 100*3*100/(100*20) = 15
    stock3 = ShopStock.objects.create(shop=shop, item=arrows, bundle_units=3, quantity=10)
    assert sell_price(stock3) == 15

    # Odd value: 100 cp per 3 units, bundle of 2 at 100% = ceil(66.67) = 67
    odd = make_stacked(club, "Odd Darts", "dart", 100, 3)
    stock_odd = ShopStock.objects.create(
        shop=shop, item=odd, bundle_units=2, quantity=10, sell_percent=100
    )
    assert sell_price(stock_odd) == 67


def test_line_sell_percent_override_wins(admin_client, club, shop, arrows):
    """Line sell_percent override wins over shop default."""
    shop.sell_percent = 100
    shop.save()
    stock = ShopStock.objects.create(
        shop=shop, item=arrows, bundle_units=5, quantity=10, sell_percent=50
    )
    # 50% of 25 = 12.5 -> ceil = 13
    assert sell_price(stock) == 13


def test_shop_percent_applied(admin_client, club, shop, arrows):
    """Shop sell_percent is applied when line has no override."""
    shop.sell_percent = 150
    shop.save()
    stock = ShopStock.objects.create(shop=shop, item=arrows, bundle_units=5, quantity=10)
    # 150% of 25 = 37.5 -> ceil = 38
    assert sell_price(stock) == 38


def test_non_stacked_price_unchanged(admin_client, club, shop):
    """Non-stacked items use floor with 1 cp minimum, unchanged from before."""
    normal = ShopStock._meta.get_field("item").related_model.objects.create(
        club=club, name="Torch", value_cp=100
    )
    stock = ShopStock.objects.create(shop=shop, item=normal, quantity=5)
    assert sell_price(stock) == 100  # 100 cp * 100% = 100 cp

    shop.sell_percent = 50
    shop.save()
    assert sell_price(stock) == 50  # floor(100 * 50 / 100) = 50

    # 1 cp minimum for non-stacked
    shop.sell_percent = 0
    shop.save()
    assert sell_price(stock) == 1  # 0% of 100 = 0, but minimum 1 cp

    # Another non-stacked item with value 1 cp
    normal2 = ShopStock._meta.get_field("item").related_model.objects.create(
        club=club, name="Candle", value_cp=1
    )
    stock2 = ShopStock.objects.create(shop=shop, item=normal2, quantity=5)
    # 0% of 1 = 0, but minimum 1 cp for non-stacked
    assert sell_price(stock2) == 1


# Permission tests
@pytest.mark.parametrize("view_name", ["stock_add", "stock_edit", "stock_remove"])
def test_player_gets_403(view_name, club, shop, player, login, arrows):
    """Player gets 403 on manage views."""
    stock = ShopStock.objects.create(shop=shop, item=arrows, bundle_units=5, quantity=10)
    ids = {
        "stock_add": [shop.pk],
        "stock_edit": [shop.pk, stock.pk],
        "stock_remove": [shop.pk, stock.pk],
    }[view_name]
    client = login(player)
    if view_name == "stock_remove":
        r = client.post(u(view_name, club, *ids))
    else:
        r = client.get(u(view_name, club, *ids))
    assert r.status_code == 403


@pytest.mark.parametrize("view_name", ["stock_add", "stock_edit", "stock_remove"])
def test_other_club_admin_gets_404(
    view_name, club, other_club, other_shop, shop, admin_client, arrows
):
    """Other-club admin gets 404 on manage views."""
    stock = ShopStock.objects.create(shop=other_shop, item=arrows, bundle_units=5, quantity=10)
    ids = {
        "stock_add": [other_shop.pk],
        "stock_edit": [other_shop.pk, stock.pk],
        "stock_remove": [other_shop.pk, stock.pk],
    }[view_name]
    if view_name == "stock_remove":
        r = admin_client.post(u(view_name, other_club, *ids))
    else:
        r = admin_client.get(u(view_name, other_club, *ids))
    assert r.status_code == 404


@pytest.mark.parametrize("view_name", ["stock_add", "stock_edit", "stock_remove"])
def test_anonymous_gets_login(view_name, club, shop, client, arrows):
    """Anonymous user gets redirected to login."""
    stock = ShopStock.objects.create(shop=shop, item=arrows, bundle_units=5, quantity=10)
    ids = {
        "stock_add": [shop.pk],
        "stock_edit": [shop.pk, stock.pk],
        "stock_remove": [shop.pk, stock.pk],
    }[view_name]
    if view_name == "stock_remove":
        r = client.post(u(view_name, club, *ids))
    else:
        r = client.get(u(view_name, club, *ids))
    assert r.status_code == 302
    assert "/accounts/login/" in r.url


@pytest.mark.story("U125")
def test_bundle_column_in_manage_page(admin_client, club, shop, arrows):
    """Manage page shows Bundle column with bundle label."""
    ShopStock.objects.create(shop=shop, item=arrows, bundle_units=5, quantity=10)
    ShopStock.objects.create(shop=shop, item=arrows, bundle_units=100, quantity=2)
    r = admin_client.get(u("manage_edit", club, shop.pk))
    assert r.status_code == 200
    html = r.content.decode()
    assert "bundle of 5 arrow" in html
    assert "bundle of 100 arrow" in html


@pytest.mark.story("U125")
def test_edit_form_bundle_units_disabled_for_non_stacked(admin_client, club, shop):
    """Edit form disables bundle_units for non-stacked items."""
    normal = ShopStock._meta.get_field("item").related_model.objects.create(
        club=club, name="Torch", value_cp=10
    )
    stock = ShopStock.objects.create(shop=shop, item=normal, quantity=5)
    r = admin_client.get(u("stock_edit", club, shop.pk, stock.pk))
    assert r.status_code == 200
    form = r.context["form"]
    assert form.fields["bundle_units"].disabled is True


@pytest.mark.story("U125")
def test_add_form_allows_stacked_item_again(admin_client, club, shop, arrows):
    """Add form allows adding a stacked item again with different bundle size."""
    ShopStock.objects.create(shop=shop, item=arrows, bundle_units=5, quantity=10)
    r = admin_client.get(u("stock_add", club, shop.pk))
    form = r.context["form"]
    # Arrows should still be in the queryset
    assert arrows in form.fields["item"].queryset
