from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404
from shops.models import Shop, ShopStock


@club_admin_required
def shop_list(request, club_slug):
    return render(request, "shops/manage/list.html")


@club_admin_required
def shop_create(request, club_slug):
    return render(request, "shops/manage/shop_form.html")


@club_admin_required
def shop_edit(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    return render(request, "shops/manage/shop_form.html", {"shop": shop})


@club_admin_required
def stock_add(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    return render(request, "shops/manage/stock_form.html", {"shop": shop})


@club_admin_required
def stock_edit(request, club_slug, shop_id, stock_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    stock = club_get_object_or_404(request, ShopStock, pk=stock_id, shop=shop)
    return render(request, "shops/manage/stock_form.html", {"shop": shop, "stock": stock})


@club_admin_required
@require_POST
def stock_remove(request, club_slug, shop_id, stock_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    club_get_object_or_404(request, ShopStock, pk=stock_id, shop=shop)
    return redirect("shops:manage_edit", club_slug=club_slug, shop_id=shop.pk)
