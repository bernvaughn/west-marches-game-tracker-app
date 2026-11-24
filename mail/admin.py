from django.contrib import admin
from django.utils import timezone

from .models import DoNotEmail, EmailMessage, JobRun


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailMessage)
class EmailMessageAdmin(ReadOnlyAdmin):
    list_display = ["status", "kind", "to_address", "attempts", "last_error", "created"]
    list_filter = ["status", "kind"]
    search_fields = ["to_address", "subject"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(DoNotEmail)
class DoNotEmailAdmin(ReadOnlyAdmin):
    list_display = ["address", "reason", "created"]
    list_filter = ["reason"]
    search_fields = ["address"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(JobRun)
class JobRunAdmin(ReadOnlyAdmin):
    list_display = ["name", "last_run_at", "ok", "note", "timer_running"]
    list_filter = ["ok", "name"]
    search_fields = ["name"]
    ordering = ["name"]

    @admin.display(description="Timer")
    def timer_running(self, obj):
        if obj.last_run_at is None:
            return "Never"
        if timezone.now() - obj.last_run_at < timezone.timedelta(minutes=15):
            return "Running"
        return "Stopped"
