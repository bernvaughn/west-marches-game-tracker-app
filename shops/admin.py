from django.contrib import admin

from .models import FavoriteShop, Rotation, Shop, ShopStock


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "building", "silhouette", "street_position"]
    list_filter = ["club", "building"]
    search_fields = ["name", "keeper_name"]
    ordering = ["name"]


@admin.register(ShopStock)
class ShopStockAdmin(admin.ModelAdmin):
    list_display = ["shop", "item", "bundle_units", "quantity"]
    list_filter = ["shop__club"]
    search_fields = ["shop__name", "item__name"]
    ordering = ["shop", "item"]


@admin.register(Rotation)
class RotationAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "open_date", "close_date"]
    list_filter = ["club"]
    search_fields = ["name"]
    date_hierarchy = "open_date"
    ordering = ["-open_date"]


@admin.register(FavoriteShop)
class FavoriteShopAdmin(admin.ModelAdmin):
    list_display = ["character", "content_object", "created_at"]
    list_filter = ["character__club"]
    search_fields = ["character__name"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
