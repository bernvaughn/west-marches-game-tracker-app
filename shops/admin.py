from django.contrib import admin

from .models import FavoriteShop, Rotation, Shop, ShopStock


class ShopStockInline(admin.TabularInline):
    model = ShopStock
    extra = 0
    show_change_link = True
    autocomplete_fields = ["item"]


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "building", "silhouette", "street_position"]
    list_filter = ["club", "building"]
    search_fields = ["name", "keeper_name"]
    ordering = ["name"]
    autocomplete_fields = ["club"]
    list_select_related = ["club"]
    inlines = [ShopStockInline]
    fieldsets = (
        ("Main", {"fields": ("club", "name", "description")}),
        (
            "Keeper and pricing",
            {"fields": ("keeper_name", "keeper_description", "sell_percent", "buy_percent")},
        ),
        (
            "Appearance",
            {
                "fields": ("color", "silhouette", "building", "street_position", "symbol"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(ShopStock)
class ShopStockAdmin(admin.ModelAdmin):
    list_display = ["shop", "item", "bundle_units", "quantity"]
    list_filter = ["shop__club"]
    search_fields = ["shop__name", "item__name"]
    ordering = ["shop", "item"]
    autocomplete_fields = ["shop", "item"]
    list_select_related = ["shop", "item"]


@admin.register(Rotation)
class RotationAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "open_date", "close_date"]
    list_filter = ["club"]
    search_fields = ["name"]
    date_hierarchy = "open_date"
    ordering = ["-open_date"]
    autocomplete_fields = ["club", "shops"]
    list_select_related = ["club"]


@admin.register(FavoriteShop)
class FavoriteShopAdmin(admin.ModelAdmin):
    list_display = ["character", "content_object", "created_at"]
    list_filter = ["character__club"]
    search_fields = ["character__name"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    autocomplete_fields = ["character"]
    readonly_fields = ["created_at"]
    list_select_related = ["character"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("content_object")
