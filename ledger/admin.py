from django.contrib import admin

from .models import LedgerEntry, LedgerLine


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LedgerLineInline(admin.TabularInline):
    model = LedgerLine
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ReadOnlyAdmin):
    list_display = ["id", "club", "character", "kind", "date"]
    list_filter = ["club", "kind"]
    inlines = [LedgerLineInline]


@admin.register(LedgerLine)
class LedgerLineAdmin(ReadOnlyAdmin):
    list_display = ["id", "entry", "item", "quantity", "coins"]
