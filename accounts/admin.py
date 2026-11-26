from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Club,
    Membership,
    Message,
    PasswordHistory,
    SiteFeedback,
    SiteSettings,
    User,
    WhitelistEntry,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "is_staff", "is_active"]
    search_fields = ["email", "display_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "must_change_password")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {"classes": ("wide",), "fields": ("email", "display_name", "password1", "password2")},
        ),
    )


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created"]
    search_fields = ["name", "slug"]
    date_hierarchy = "created"
    ordering = ["name"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "club", "is_club_admin", "is_game_master", "created"]
    list_filter = ["club", "is_club_admin", "is_game_master"]
    search_fields = ["user__email", "user__display_name", "club__name"]
    autocomplete_fields = ["user", "club"]


@admin.register(WhitelistEntry)
class WhitelistEntryAdmin(admin.ModelAdmin):
    list_display = ["email", "club", "created"]
    list_filter = ["club"]
    search_fields = ["email"]
    autocomplete_fields = ["club"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "club", "sender", "character", "kind", "status", "created"]
    list_filter = ["club", "kind", "status"]
    search_fields = ["body", "sender__user__email", "character__name"]
    autocomplete_fields = ["club", "sender", "character"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(SiteFeedback)
class SiteFeedbackAdmin(admin.ModelAdmin):
    list_display = ["kind", "status", "user", "club", "created"]
    list_filter = ["club", "kind", "status"]
    search_fields = ["body", "user__email", "club__name"]
    autocomplete_fields = ["user", "club"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ["donate_url"]
    search_fields = ["donate_url"]
    ordering = ["-pk"]


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(ReadOnlyAdmin):
    list_display = ["user", "created"]
    list_filter = ["user"]
    search_fields = ["user__email", "user__display_name"]
    date_hierarchy = "created"
    ordering = ["-created"]
    autocomplete_fields = ["user"]
