"""Tests for the shared item picker widget in shop stock forms."""

import pytest
from django.urls import reverse

from items.models import Item
from items.widgets import ItemPickerWidget
from shops.forms.manage import StockAddForm
from shops.models import ShopStock

pytestmark = pytest.mark.django_db


def u(name, club, *ids):
    keys = {"stock_add": ["shop_id"]}[name]
    kwargs = {"club_slug": club.slug, **dict(zip(keys, ids, strict=True))}
    return reverse(f"shops:{name}", kwargs=kwargs)


@pytest.fixture
def admin_client(club_admin, login):
    return login(club_admin)


@pytest.fixture
def stacked_item(club):
    """A stacked item (e.g., arrows) with value."""
    return Item.objects.create(
        club=club, name="Arrow", value_cp=5, is_stacked=True, value_units=20, unit_name="arrow"
    )


@pytest.fixture
def plain_item(club):
    """A plain (non-stacked) item with value."""
    return Item.objects.create(club=club, name="Longsword", value_cp=1500)


@pytest.fixture
def no_value_item(club):
    """An item with no value."""
    return Item.objects.create(club=club, name="Rope", value_cp=0)


@pytest.mark.story("S5")
def test_stock_add_form_uses_item_picker_widget(shop, plain_item):
    """StockAddForm's item field uses ItemPickerWidget."""
    form = StockAddForm(shop=shop)
    assert isinstance(form.fields["item"].widget, ItemPickerWidget)
    assert form.fields["item"].widget.club == shop.club


@pytest.mark.story("S5")
def test_stock_add_form_queryset_excludes_retired_and_existing_non_stacked(club, shop, plain_item):
    """Queryset excludes retired items and non-stacked items already in stock."""
    Item.objects.create(club=club, name="Old Sword", value_cp=100, retired=True)
    ShopStock.objects.create(shop=shop, item=plain_item, quantity=1)
    fresh = Item.objects.create(club=club, name="Fresh Sword", value_cp=200)

    form = StockAddForm(shop=shop)
    qs = form.fields["item"].queryset
    assert list(qs) == [fresh]


@pytest.mark.story("S5")
def test_stock_add_form_allows_multiple_stacked_bundles(club, shop, stacked_item):
    """Stacked items can have multiple bundle sizes in stock."""
    ShopStock.objects.create(shop=shop, item=stacked_item, bundle_units=10, quantity=5)
    fresh_stacked = Item.objects.create(
        club=club, name="Bolt", value_cp=10, is_stacked=True, value_units=10, unit_name="bolt"
    )

    form = StockAddForm(shop=shop)
    qs = form.fields["item"].queryset
    # Both stacked items should be available
    assert stacked_item in qs
    assert fresh_stacked in qs


@pytest.mark.story("S5")
def test_saved_stock_data_identical_to_before(admin_client, club, shop, plain_item):
    """POSTing to stock_add saves the same data as before the picker change."""
    url = u("stock_add", club, shop.pk)
    response = admin_client.post(url, {"item": plain_item.pk, "quantity": "3", "bundle_units": "1"})
    assert response.status_code == 302

    stock = ShopStock.objects.get(shop=shop, item=plain_item)
    assert stock.quantity == 3
    assert stock.bundle_units == 1
    assert stock.sell_percent is None
    assert stock.buy_percent is None


@pytest.mark.story("S5")
def test_stock_add_page_renders_picker_widget(admin_client, club, shop):
    """The stock add page renders the picker widget (search input, hidden input)."""
    url = u("stock_add", club, shop.pk)
    response = admin_client.get(url)
    assert response.status_code == 200

    html = response.content.decode()
    # Widget renders search input and hidden input
    assert 'type="search"' in html
    assert 'placeholder="Search items by name, type, or trait..."' in html
    assert 'name="item"' in html
    assert 'type="hidden"' in html
    # The "New item" button is still present
    assert "New item" in html


@pytest.mark.story("S5")
def test_browse_catalogue_button_still_works(admin_client, club, shop):
    """The 'New item' button (create new item) is still present and functional."""
    url = u("stock_add", club, shop.pk)
    response = admin_client.get(url)
    html = response.content.decode()

    # The button to create a new item is still there (URL is /c/<club>/items/new/)
    assert f"/c/{club.slug}/items/new/" in html
    assert "New item" in html


@pytest.mark.story("S5")
def test_stock_add_form_validation_unchanged(admin_client, club, shop, plain_item, stacked_item):
    """Form validation works identically to before."""
    url = u("stock_add", club, shop.pk)

    # Valid submission with plain item
    response = admin_client.post(url, {"item": plain_item.pk, "quantity": "5", "bundle_units": "1"})
    assert response.status_code == 302

    # Duplicate non-stacked item rejected
    response = admin_client.post(url, {"item": plain_item.pk, "quantity": "2", "bundle_units": "1"})
    assert response.status_code == 200
    form = response.context["form"]
    assert form.errors

    # Non-stacked item with bundle_units != 1 rejected (use a different plain item)
    plain_item_2 = Item.objects.create(club=club, name="Dagger", value_cp=200)
    response = admin_client.post(
        url, {"item": plain_item_2.pk, "quantity": "1", "bundle_units": "5"}
    )
    assert response.status_code == 200
    form = response.context["form"]
    assert "bundle_units" in form.errors

    # Stacked item with bundle_units > 1 accepted
    response = admin_client.post(
        url, {"item": stacked_item.pk, "quantity": "10", "bundle_units": "20"}
    )
    assert response.status_code == 302


@pytest.mark.story("S5")
def test_widget_search_url_includes_club_slug(shop):
    """The widget's search URL includes the club slug."""
    form = StockAddForm(shop=shop)
    widget = form.fields["item"].widget
    context = widget.get_context("item", None, {})
    assert f"/c/{shop.club.slug}/items/picker/search/" in context["widget"]["search_url"]
