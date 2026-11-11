from django.shortcuts import render

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from shops.models import Shop, ShopStock


@club_member_required
def buy(request, club_slug, shop_id, stock_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    stock = club_get_object_or_404(request, ShopStock, pk=stock_id, shop=shop)
    return render(request, "shops/buy/buy.html", {"shop": shop, "stock": stock})
