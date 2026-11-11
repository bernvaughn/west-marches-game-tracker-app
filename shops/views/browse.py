from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import club_member_required, is_club_admin
from accounts.scoping import club_get_object_or_404
from shops.models import Shop, ShopStock
from shops.services import is_open, open_shops, sell_price


def _load_shop(request, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    open_now = is_open(shop, timezone.localdate())
    if not open_now and not is_club_admin(request.user, request.club):
        raise Http404
    return shop, open_now


def _visible_rows(shop):
    stocks = (
        ShopStock.objects.filter(shop=shop, item__retired=False)
        .exclude(quantity=0)
        .select_related("item", "shop")
        .order_by("item__name")
    )
    rows = list(stocks)
    for stock in rows:
        stock.price = sell_price(stock)
    return rows


@club_member_required
def index(request, club_slug):
    shops = open_shops(request.club, timezone.localdate())
    return render(request, "shops/browse/index.html", {"shops": shops})


@club_member_required
def shop_detail(request, club_slug, shop_id):
    shop, open_now = _load_shop(request, shop_id)
    context = {"shop": shop, "is_open": open_now, "rows": _visible_rows(shop)}
    return render(request, "shops/browse/detail.html", context)


@club_member_required
def stock_fragment(request, club_slug, shop_id):
    shop, _ = _load_shop(request, shop_id)
    return render(request, "shops/browse/_stock.html", {"shop": shop, "rows": _visible_rows(shop)})
