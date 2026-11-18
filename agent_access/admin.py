from django.contrib import admin

from .models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine, TokenAuditLog


@admin.register(TokenAuditLog)
class TokenAuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "user", "club", "connection", "timestamp"]
    list_filter = ["action", "club", "timestamp"]
    search_fields = ["user__email", "user__display_name", "connection__label"]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]


admin.site.register([AgentConnection, ProposedBatch, ProposedItem, ProposedLine])
