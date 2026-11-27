from django.contrib import admin

from .models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine, TokenAuditLog


@admin.register(TokenAuditLog)
class TokenAuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "user", "club", "connection", "timestamp"]
    list_filter = ["action", "club", "timestamp"]
    search_fields = ["user__email", "user__display_name", "connection__label"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]
    autocomplete_fields = ["user", "club", "connection"]
    readonly_fields = ["timestamp"]
    list_select_related = ["user", "club", "connection"]


@admin.register(AgentConnection)
class AgentConnectionAdmin(admin.ModelAdmin):
    list_display = ["label", "user", "club", "kind", "created"]
    list_filter = ["club", "kind"]
    search_fields = ["label", "user__email"]
    date_hierarchy = "created"
    ordering = ["-created"]
    autocomplete_fields = ["user", "club", "oauth_application"]
    readonly_fields = ["created", "token_prefix", "last_used_at"]
    exclude = ["token_hash"]
    list_select_related = ["user", "club"]


class ProposedLineInline(admin.TabularInline):
    model = ProposedLine
    extra = 0
    show_change_link = True
    autocomplete_fields = ["item", "character", "proposed_item"]


@admin.register(ProposedBatch)
class ProposedBatchAdmin(admin.ModelAdmin):
    list_display = ["id", "club", "connection", "user", "date", "status", "created"]
    list_filter = ["club", "status"]
    search_fields = ["connection__label", "user__email", "idempotency_key"]
    date_hierarchy = "created"
    ordering = ["-created"]
    autocomplete_fields = ["club", "connection", "user", "confirmed_by", "reversed_by"]
    readonly_fields = ["created", "confirmed_at", "reversed_at"]
    inlines = [ProposedLineInline]
    list_select_related = ["club", "connection", "user"]


@admin.register(ProposedItem)
class ProposedItemAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "status", "batch", "created"]
    list_filter = ["club", "status"]
    search_fields = ["name"]
    date_hierarchy = "created"
    ordering = ["-created"]
    autocomplete_fields = ["club", "approved_item", "batch", "connection"]
    readonly_fields = ["created"]
    list_select_related = ["club", "batch"]


@admin.register(ProposedLine)
class ProposedLineAdmin(admin.ModelAdmin):
    list_display = ["batch", "character", "item", "quantity", "coins", "date"]
    list_filter = ["batch__club"]
    search_fields = ["character__name", "item__name"]
    ordering = ["-batch__created"]
    autocomplete_fields = ["batch", "character", "item", "proposed_item"]
    list_select_related = ["batch", "character", "item"]
