from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404, club_queryset
from items.stacked import sale_price
from shops.forms.manage import ShopForm, StockAddForm, StockEditForm, StreetSettingsForm
from shops.models import Shop, ShopStock
from shops.services import open_shops, ordered_shops, percent_price, sell_price, set_street_order
from shops.views.browse import STREET_ROW, street_lots, street_stalls


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
def street_editor(request, club_slug):
    """Drag-and-drop grid to set the club's shop street order visually."""
    if request.method == "POST":
        # The JS joins the ordered IDs into one comma-separated value; accept
        # either that or several shop_order values (e.g. direct form posts).
        raw = request.POST.getlist("shop_order")
        ordered = []
        for value in raw:
            ordered.extend([part.strip() for part in value.split(",") if part.strip()])
        set_street_order(request.club, ordered)
        messages.success(request, "Street order saved.")
        return redirect("shops:street_editor", club_slug=club_slug)
    shops = ordered_shops(club_queryset(request, Shop))
    stalls = street_stalls(request.club)
    lots = street_lots(
        shops,
        stalls,
        min_gap=request.club.street_min_gap,
        max_gap=request.club.street_max_gap,
        stall_gap=request.club.street_stall_gap,
        per_row=STREET_ROW,
    )
    return render(
        request,
        "shops/manage/street_editor.html",
        {"lots": lots, "shops": shops, "stalls": stalls},
    )


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
    for stock in shop.stock.select_related("item").order_by("item__name", "bundle_units"):
        buy = stock.buy_percent if stock.buy_percent is not None else shop.buy_percent
        if stock.item.is_stacked:
            buy_price = sale_price(stock.item, stock.bundle_units, buy)
        else:
            buy_price = percent_price(stock.item.value_cp, buy)
        rows.append(
            {
                "stock": stock,
                "sell_price": sell_price(stock),
                "buy_price": buy_price,
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
