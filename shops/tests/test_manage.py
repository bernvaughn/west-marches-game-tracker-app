import pytest
from django.urls import reverse

from items.models import Item
from shops.forms.manage import StockAddForm
from shops.models import Shop, ShopStock
from shops.services import buy_price, sell_price

pytestmark = pytest.mark.django_db


def u(name, club, *ids):
    keys = {"manage_list": [], "manage_create": [], "manage_edit": ["shop_id"],
            "stock_add": ["shop_id"], "stock_edit": ["shop_id", "stock_id"],
            "stock_remove": ["shop_id", "stock_id"]}[name]  # fmt: skip
    kwargs = {"club_slug": club.slug, **dict(zip(keys, ids, strict=True))}
    return reverse(f"shops:{name}", kwargs=kwargs)


@pytest.fixture
def admin_client(club_admin, login):
    return login(club_admin)


@pytest.fixture
def shop_b(club):
    return Shop.objects.create(club=club, name="Second", sell_percent=100, buy_percent=50)


def shop_data(**over):
    data = {"name": "Lantern", "description": "", "keeper_name": "", "keeper_description": "",
            "color": "parchment", "symbol": "",
            "sell_percent": "100", "buy_percent": "50"}  # fmt: skip
    data.update(over)
    return data


@pytest.mark.story("S1")
def test_defaults_change_prices(admin_client, club, shop, stock):
    assert sell_price(stock) == 100 and buy_price(shop, stock.item) == 50
    r = admin_client.post(u("manage_edit", club, shop.pk),
                          shop_data(sell_percent="200", buy_percent="10"))  # fmt: skip
    assert r.status_code == 302
    stock.refresh_from_db()
    shop.refresh_from_db()
    assert sell_price(stock) == 200 and buy_price(shop, stock.item) == 10
    page = admin_client.get(u("manage_edit", club, shop.pk))
    assert b"Unlimited" not in page.content
    assert "2 sp" in page.content.decode() or "200" in page.content.decode()


@pytest.mark.story("S1")
def test_override_scoped_to_one_shop(admin_client, club, shop, shop_b, item, stock):
    other = ShopStock.objects.create(shop=shop_b, item=item, quantity=1)
    r = admin_client.post(u("stock_edit", club, shop.pk, stock.pk),
                          {"quantity": "2", "sell_percent": "300",
                           "buy_percent": "80"})  # fmt: skip
    assert r.status_code == 302
    stock.refresh_from_db()
    assert sell_price(stock) == 300 and buy_price(shop, item) == 80
    assert sell_price(other) == 100 and buy_price(shop_b, item) == 50


@pytest.mark.story("U4")
def test_add_restock_remove(admin_client, club, shop, item):
    r = admin_client.post(u("stock_add", club, shop.pk), {"item": item.pk, "quantity": "5"})
    assert r.status_code == 302
    stock = ShopStock.objects.get(shop=shop, item=item)
    assert stock.quantity == 5 and stock.sell_percent is None
    admin_client.post(u("stock_edit", club, shop.pk, stock.pk), {"quantity": "9"})
    stock.refresh_from_db()
    assert stock.quantity == 9
    assert admin_client.get(u("stock_remove", club, shop.pk, stock.pk)).status_code == 405
    admin_client.post(u("stock_remove", club, shop.pk, stock.pk))
    assert not ShopStock.objects.filter(pk=stock.pk).exists()


@pytest.mark.story("U4")
def test_edit_page_shows_soldout_and_retired(admin_client, club, shop, item):
    ShopStock.objects.create(shop=shop, item=item, quantity=0)
    old = Item.objects.create(club=club, name="Relic", value_cp=5, retired=True)
    ShopStock.objects.create(shop=shop, item=old, quantity=1)
    html = admin_client.get(u("manage_edit", club, shop.pk)).content.decode()
    assert "Sold out" in html and "Retired" in html and "Relic" in html


@pytest.mark.story("U9")
def test_blank_quantity_is_unlimited(admin_client, club, shop, item):
    admin_client.post(u("stock_add", club, shop.pk), {"item": item.pk, "quantity": ""})
    stock = ShopStock.objects.get(shop=shop, item=item)
    assert stock.quantity is None
    assert b"Unlimited" in admin_client.get(u("manage_edit", club, shop.pk)).content
    admin_client.post(u("stock_edit", club, shop.pk, stock.pk), {"quantity": "3"})
    stock.refresh_from_db()
    assert stock.quantity == 3
    admin_client.post(u("stock_edit", club, shop.pk, stock.pk), {"quantity": ""})
    stock.refresh_from_db()
    assert stock.quantity is None


@pytest.mark.story("U10")
def test_create_shop_with_look(admin_client, club):
    r = admin_client.post(u("manage_create", club),
                          shop_data(keeper_name="Marta", keeper_description="Stout",
                                    color="ocean", symbol="⚓"))  # fmt: skip
    assert r.status_code == 302
    shop = Shop.objects.get(club=club, name="Lantern")
    assert (shop.keeper_name, shop.keeper_description) == ("Marta", "Stout")
    assert (shop.color, shop.symbol) == ("ocean", "⚓")


@pytest.mark.story("U10")
def test_invalid_color_refused(admin_client, club, shop):
    r = admin_client.post(u("manage_edit", club, shop.pk), shop_data(color="pink"))
    assert r.status_code == 200
    shop.refresh_from_db()
    assert shop.color == "parchment"
    r = admin_client.post(u("manage_create", club), shop_data(name="New", color="pink"))
    assert r.status_code == 200 and not Shop.objects.filter(name="New").exists()


@pytest.mark.story("S1")
def test_new_shop_defaults_and_percent_bounds(admin_client, club):
    page = admin_client.get(u("manage_create", club))
    form = page.context["form"]
    assert form["sell_percent"].value() == 100 and form["buy_percent"].value() == 50
    r = admin_client.post(u("manage_create", club), shop_data(name="Hi", sell_percent="1001"))
    assert r.status_code == 200 and not Shop.objects.filter(name="Hi").exists()
    admin_client.post(u("manage_create", club),
                      shop_data(name="Lo", sell_percent="0", buy_percent="1000"))  # fmt: skip
    assert Shop.objects.filter(name="Lo").exists()


@pytest.mark.story("S1")
def test_override_percent_bounds(admin_client, club, shop, stock):
    r = admin_client.post(u("stock_edit", club, shop.pk, stock.pk),
                          {"quantity": "1", "sell_percent": "1001"})  # fmt: skip
    assert r.status_code == 200


@pytest.mark.story("S1")
def test_list_status_and_count(admin_client, club, shop, always_open, closed_shop, stock):
    page = admin_client.get(u("manage_list", club))
    rows = {s.name: (o, s.stock_count) for s, o in page.context["rows"]}
    assert rows["Lantern"] == (True, 1)
    assert rows["Shuttered"] == (False, 0)
    html = page.content.decode()
    assert "Open" in html and "Closed" in html


@pytest.mark.story("U4")
def test_item_choices(club, other_club, shop, item):
    Item.objects.create(club=club, name="Old", value_cp=1, retired=True)
    Item.objects.create(club=other_club, name="Foreign", value_cp=1)
    fresh = Item.objects.create(club=club, name="Fresh", value_cp=1)
    ShopStock.objects.create(shop=shop, item=item, quantity=1)
    qs = StockAddForm(shop=shop).fields["item"].queryset
    assert list(qs) == [fresh]


@pytest.mark.story("S1")
@pytest.mark.parametrize("name", ["manage_list", "manage_create", "manage_edit", "stock_add",
                                  "stock_edit"])  # fmt: skip
def test_non_admins_403_admin_ok(name, club, shop, stock, player, game_master, site_admin, login):
    ids = {"manage_list": [], "manage_create": [], "manage_edit": [shop.pk],
           "stock_add": [shop.pk], "stock_edit": [shop.pk, stock.pk]}[name]  # fmt: skip
    url = u(name, club, *ids)
    assert login(player).get(url).status_code == 403
    assert login(game_master).get(url).status_code == 403
    assert login(site_admin).get(url).status_code == 200
    rm = u("stock_remove", club, shop.pk, stock.pk)
    assert login(player).post(rm).status_code == 403


@pytest.mark.story("S1")
def test_cross_club_404(admin_client, club, other_shop, shop, shop_b, item, other_club):
    assert admin_client.get(u("manage_edit", club, other_shop.pk)).status_code == 404
    assert admin_client.get(u("stock_add", club, other_shop.pk)).status_code == 404
    foreign_item = Item.objects.create(club=other_club, name="F", value_cp=1)
    foreign = ShopStock.objects.create(shop=other_shop, item=foreign_item, quantity=1)
    assert admin_client.get(u("stock_edit", club, other_shop.pk, foreign.pk)).status_code == 404
    assert admin_client.post(u("stock_remove", club, other_shop.pk, foreign.pk)).status_code == 404
    mine = ShopStock.objects.create(shop=shop_b, item=item, quantity=1)
    assert admin_client.get(u("stock_edit", club, shop.pk, mine.pk)).status_code == 404
    assert admin_client.post(u("stock_remove", club, shop.pk, mine.pk)).status_code == 404
    assert ShopStock.objects.filter(pk=mine.pk).exists()
