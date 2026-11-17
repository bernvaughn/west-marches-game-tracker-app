from django.contrib import admin

from .models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine, TokenAuditLog


@admin.register(TokenAuditLog)
class TokenAuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "club", "connection", "user", "action"]
    list_filter = ["action", "club", "timestamp"]
    search_fields = ["connection__label", "user__email"]
    readonly_fields = ["timestamp", "club", "connection", "user", "action", "details"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]


admin.site.register([AgentConnection, ProposedBatch, ProposedItem, ProposedLine])
