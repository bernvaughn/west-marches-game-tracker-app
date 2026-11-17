from django.contrib import admin

from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "rarity", "magic_type", "value_cp"]
    list_filter = ["club", "rarity", "magic_type"]
    search_fields = ["name", "description"]
    autocomplete_fields = ["club"]
