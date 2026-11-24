from django.contrib import admin
from django.utils import timezone

from .models import (
    ClubMailSettings,
    DoNotEmail,
    EmailMessage,
    EmailPreference,
    JobRun,
    NoticeSent,
    OneTimeToken,
)


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


@admin.register(ClubMailSettings)
class ClubMailSettingsAdmin(admin.ModelAdmin):
    """Per-club mail settings. The contact email is the reply-to on club emails."""

    list_display = ["club", "contact_email", "reminder_days"]
    search_fields = ["club__name", "club__slug", "contact_email"]
    raw_id_fields = ["club"]
    ordering = ["club__name"]
    list_select_related = ["club"]


@admin.register(EmailPreference)
class EmailPreferenceAdmin(ReadOnlyAdmin):
    """A member's opt-in or opt-out per mail kind. Read-only: only the member changes it."""

    list_display = ["email", "club", "kind", "enabled"]
    list_filter = ["kind", "enabled"]
    search_fields = ["membership__user__email", "membership__club__name"]
    list_select_related = ["membership__user", "membership__club"]
    ordering = ["membership__club__name", "membership__user__email", "kind"]

    @admin.display(description="Email", ordering="membership__user__email")
    def email(self, obj):
        return obj.membership.user.email

    @admin.display(description="Club", ordering="membership__club__name")
    def club(self, obj):
        return obj.membership.club


@admin.register(NoticeSent)
class NoticeSentAdmin(ReadOnlyAdmin):
    """Which reminder, cancel, change and digest notices were already sent, to avoid resending."""

    list_display = ["kind", "key", "user", "created"]
    list_filter = ["kind"]
    search_fields = ["key", "user__email"]
    list_select_related = ["user"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(OneTimeToken)
class OneTimeTokenAdmin(ReadOnlyAdmin):
    """Sign-in, reset and RSVP tokens. Read-only, and the hash and extra data are never shown."""

    list_display = ["purpose", "user", "club", "created", "expires_at", "state"]
    list_filter = ["purpose"]
    search_fields = ["user__email"]
    list_select_related = ["user", "club"]
    date_hierarchy = "created"
    ordering = ["-created"]
    # token_hash is the credential; extra can hold a pending new email address.
    exclude = ["token_hash", "extra"]

    @admin.display(description="State")
    def state(self, obj):
        if obj.used_at is not None:
            return "Used"
        if obj.expires_at < timezone.now():
            return "Expired"
        return "Unused"
