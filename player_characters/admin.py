from django.contrib import admin

from .models import Character, CharacterStatusChange


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "owner", "level", "char_class", "died_on", "archived_at"]
    list_filter = ["club", "level", "died_on", "archived_at"]
    search_fields = ["name", "char_class"]
    autocomplete_fields = ["club", "owner"]
    readonly_fields = ["last_printed_at"]


@admin.register(CharacterStatusChange)
class CharacterStatusChangeAdmin(admin.ModelAdmin):
    list_display = ["character", "kind", "by", "at", "date"]
    list_filter = ["kind", "at"]
    search_fields = ["character__name", "by__user__display_name"]
    readonly_fields = ["character", "kind", "by", "at", "note", "date"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
