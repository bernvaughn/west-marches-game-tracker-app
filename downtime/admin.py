from django.contrib import admin

from .models import (
    DowntimeAction,
    DowntimeEntry,
    DowntimeEntryItem,
    DowntimePointEntry,
    DowntimePointRequest,
    DowntimeResult,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Base admin that disables add, change, and delete."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DowntimePointEntry)
class DowntimePointEntryAdmin(ReadOnlyAdmin):
    list_display = ["character", "delta", "kind", "date", "created_by"]
    list_filter = ["character__club", "kind"]
    search_fields = ["character__name", "note", "source"]
    date_hierarchy = "date"
    ordering = ["-date", "-id"]


@admin.register(DowntimeAction)
class DowntimeActionAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "cost", "start_date", "end_date"]
    list_filter = ["club"]
    search_fields = ["name"]
    date_hierarchy = "start_date"
    ordering = ["name"]
    autocomplete_fields = ["club"]


@admin.register(DowntimeEntry)
class DowntimeEntryAdmin(admin.ModelAdmin):
    list_display = ["action", "label", "weight", "coins", "order"]
    list_filter = ["action__club"]
    search_fields = ["label"]
    autocomplete_fields = ["action"]
    ordering = ["order"]


@admin.register(DowntimeEntryItem)
class DowntimeEntryItemAdmin(admin.ModelAdmin):
    list_display = ["entry", "item", "quantity"]
    list_filter = ["entry__action__club"]
    search_fields = ["item__name"]
    autocomplete_fields = ["entry", "item"]


@admin.register(DowntimeResult)
class DowntimeResultAdmin(ReadOnlyAdmin):
    list_display = ["character", "action", "entry", "created"]
    list_filter = ["character__club"]
    search_fields = ["character__name", "action__name"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(DowntimePointRequest)
class DowntimePointRequestAdmin(admin.ModelAdmin):
    list_display = ["club", "requested_by", "points", "status", "created"]
    list_filter = ["club", "status"]
    search_fields = ["requested_by__user__email", "note"]
    date_hierarchy = "created"
    ordering = ["-created"]
    autocomplete_fields = ["club", "requested_by", "decided_by"]
    actions = ["approve_requests", "decline_requests"]

    @admin.action(description="Approve selected requests")
    def approve_requests(self, request, queryset):
        from django.utils import timezone

        queryset.filter(status=DowntimePointRequest.Status.PENDING).update(
            status=DowntimePointRequest.Status.APPROVED,
            decided_at=timezone.now(),
        )

    @admin.action(description="Decline selected requests")
    def decline_requests(self, request, queryset):
        from django.utils import timezone

        queryset.filter(status=DowntimePointRequest.Status.PENDING).update(
            status=DowntimePointRequest.Status.DECLINED,
            decided_at=timezone.now(),
        )
