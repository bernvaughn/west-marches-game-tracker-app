from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404, club_queryset
from shops.forms.manage import ShopForm, StockAddForm, StockEditForm, StreetSettingsForm
from shops.models import Shop, ShopStock
from shops.services import open_shops, ordered_shops, percent_price


def _back(club_slug, shop):
    return redirect("shops:manage_edit", club_slug=club_slug, shop_id=shop.pk)


def _list_context(request, street_form):
    shops = ordered_shops(club_queryset(request, Shop)).annotate(stock_count=Count("stock"))
    open_ids = set(open_shops(request.club, timezone.localdate()).values_list("pk", flat=True))
    rows = [(shop, shop.pk in open_ids) for shop in shops]
    return {"rows": rows, "street_form": street_form}


@club_admin_required
def shop_list(request, club_slug):
    context = _list_context(request, StreetSettingsForm(instance=request.club))
    return render(request, "shops/manage/list.html", context)


@club_admin_required
@require_POST
def street_settings(request, club_slug):
    form = StreetSettingsForm(request.POST, instance=request.club)
    if form.is_valid():
        form.save()
        messages.success(request, "Street settings saved.")
        return redirect("shops:manage_list", club_slug=club_slug)
    return render(request, "shops/manage/list.html", _list_context(request, form))


@club_admin_required
def shop_create(request, club_slug):
    form = ShopForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        shop = form.save(commit=False)
        shop.club = request.club
        shop.save()
        messages.success(request, "Shop created.")
        return _back(club_slug, shop)
    return render(request, "shops/manage/shop_form.html", {"form": form})


@club_admin_required
def shop_edit(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    form = ShopForm(request.POST or None, instance=shop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shop saved.")
        return _back(club_slug, shop)
    rows = []
    for stock in shop.stock.select_related("item").order_by("item__name"):
        sell = stock.sell_percent if stock.sell_percent is not None else shop.sell_percent
        buy = stock.buy_percent if stock.buy_percent is not None else shop.buy_percent
        rows.append(
            {
                "stock": stock,
                "sell_price": percent_price(stock.item.value_cp, sell),
                "buy_price": percent_price(stock.item.value_cp, buy),
            }
        )
    return render(
        request, "shops/manage/shop_form.html", {"form": form, "shop": shop, "rows": rows}
    )


@club_admin_required
def stock_add(request, club_slug, shop_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    form = StockAddForm(request.POST or None, shop=shop)
    if request.method != "POST":
        preselect = request.GET.get("item", "")
        if preselect.isdigit() and form.fields["item"].queryset.filter(pk=int(preselect)).exists():
            form.initial["item"] = int(preselect)
    if request.method == "POST" and form.is_valid():
        stock = form.save(commit=False)
        stock.shop = shop
        stock.save()
        messages.success(request, "Item added.")
        return _back(club_slug, shop)
    return render(request, "shops/manage/stock_form.html", {"shop": shop, "form": form})


@club_admin_required
def stock_edit(request, club_slug, shop_id, stock_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    stock = club_get_object_or_404(request, ShopStock, pk=stock_id, shop=shop)
    form = StockEditForm(request.POST or None, instance=stock)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Stock saved.")
        return _back(club_slug, shop)
    return render(
        request, "shops/manage/stock_form.html", {"shop": shop, "stock": stock, "form": form}
    )


@club_admin_required
@require_POST
def stock_remove(request, club_slug, shop_id, stock_id):
    shop = club_get_object_or_404(request, Shop, pk=shop_id)
    stock = club_get_object_or_404(request, ShopStock, pk=stock_id, shop=shop)
    stock.delete()
    messages.success(request, "Item removed.")
    return _back(club_slug, shop)
