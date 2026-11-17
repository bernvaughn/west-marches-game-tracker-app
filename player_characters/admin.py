from django.contrib import admin

from .models import Character, Trade, TradeLine


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "owner", "level", "char_class"]
    list_filter = ["club", "level"]
    search_fields = ["name", "char_class"]
    autocomplete_fields = ["club", "owner"]


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ["id", "club", "sender", "receiver", "status", "created"]
    list_filter = ["club", "status"]
    search_fields = ["sender__name", "receiver__name"]
    autocomplete_fields = ["club", "sender", "receiver"]


@admin.register(TradeLine)
class TradeLineAdmin(admin.ModelAdmin):
    list_display = ["trade", "from_sender", "item", "quantity", "coins"]
    list_filter = ["trade__club", "trade__status"]
    autocomplete_fields = ["item"]
    search_fields = ["item__name"]