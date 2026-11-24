from django.contrib import admin

from .models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine, TokenAuditLog


@admin.register(TokenAuditLog)
class TokenAuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "user", "club", "connection", "timestamp"]
    list_filter = ["action", "club", "timestamp"]
    search_fields = ["user__email", "user__display_name", "connection__label"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]


@admin.register(AgentConnection)
class AgentConnectionAdmin(admin.ModelAdmin):
    list_display = ["label", "user", "club", "kind", "created"]
    list_filter = ["club", "kind"]
    search_fields = ["label", "user__email"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(ProposedBatch)
class ProposedBatchAdmin(admin.ModelAdmin):
    list_display = ["id", "club", "connection", "user", "date", "status", "created"]
    list_filter = ["club", "status"]
    search_fields = ["connection__label", "user__email", "idempotency_key"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(ProposedItem)
class ProposedItemAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "status", "batch", "created"]
    list_filter = ["club", "status"]
    search_fields = ["name"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(ProposedLine)
class ProposedLineAdmin(admin.ModelAdmin):
    list_display = ["batch", "character", "item", "quantity", "coins", "date"]
    list_filter = ["batch__club"]
    search_fields = ["character__name", "item__name"]
    ordering = ["-batch__created"]
