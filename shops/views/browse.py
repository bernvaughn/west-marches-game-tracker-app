from django.shortcuts import render

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from shops.models import Shop


@club_member_required
def index(request, club_slug):
    return render(request, "shops/browse/index.html")


@club_member_required
def shop_detail(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    return render(request, "shops/browse/detail.html", {"shop": shop})


@club_member_required
def stock_fragment(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    return render(request, "shops/browse/_stock.html", {"shop": shop})
