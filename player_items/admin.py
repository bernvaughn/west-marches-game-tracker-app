from django.contrib import admin

from .models import PlayerItem, PlayerItemChange, PlayerNotice


class ReadOnlyAdmin(admin.ModelAdmin):
    """Base admin that disables add, change, and delete."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PlayerItem)
class PlayerItemAdmin(admin.ModelAdmin):
    """Player-written items. Editable in admin."""

    list_display = ["character", "name", "quantity", "review", "created"]
    list_filter = ["review", "club"]
    search_fields = ["name", "character__name", "club__name"]
    list_select_related = ["character", "club", "resolved_by_change"]
    ordering = ["-created"]
    raw_id_fields = ["character", "club", "resolved_by_change"]
    readonly_fields = ["name_key", "created", "updated"]
    fields = [
        "club",
        "character",
        "name",
        "name_key",
        "quantity",
        "note",
        "review",
        "resolved_by_change",
        "created",
        "updated",
    ]


@admin.register(PlayerItemChange)
class PlayerItemChangeAdmin(ReadOnlyAdmin):
    """Append-only history of player item changes. Read-only in admin."""

    list_display = ["character", "kind", "old_name", "new_name", "quantity", "by", "at"]
    list_filter = ["kind", "club"]
    search_fields = ["old_name", "new_name", "character__name", "club__name"]
    list_select_related = ["character", "club", "item", "by"]
    ordering = ["-at", "-id"]
    date_hierarchy = "at"
    readonly_fields = [
        "club",
        "character",
        "kind",
        "old_name",
        "new_name",
        "quantity",
        "item",
        "by",
        "at",
        "note",
    ]


@admin.register(PlayerNotice)
class PlayerNoticeAdmin(ReadOnlyAdmin):
    """Player notices. Read-only in admin."""

    list_display = ["membership", "kind", "character", "created", "dismissed_at"]
    list_filter = ["kind", "club"]
    search_fields = ["text", "membership__user__email", "character__name"]
    list_select_related = ["membership__user", "club", "character"]
    ordering = ["-created", "-id"]
    date_hierarchy = "created"
    readonly_fields = [
        "membership",
        "club",
        "character",
        "kind",
        "text",
        "created",
        "dismissed_at",
    ]
