from django.shortcuts import render

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from shops.models import Shop


@club_member_required
def sell(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    return render(request, "shops/sell/sell.html", {"shop": shop})
