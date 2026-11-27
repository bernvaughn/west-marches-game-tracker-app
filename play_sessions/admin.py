from django.contrib import admin

from .models import (
    AttendanceChange,
    AttendanceHint,
    PlayerRSVP,
    PlaySession,
    SessionAttendance,
    SessionAward,
    SessionSettings,
)


class PlayerRSVPInline(admin.TabularInline):
    model = PlayerRSVP
    extra = 0
    show_change_link = True
    autocomplete_fields = ["member", "answered_by"]
    readonly_fields = ["answered_at"]


class SessionAttendanceInline(admin.TabularInline):
    model = SessionAttendance
    extra = 0
    show_change_link = True
    autocomplete_fields = ["character", "confirmed_by"]
    readonly_fields = ["confirmed_at"]


class SessionAwardInline(admin.TabularInline):
    model = SessionAward
    extra = 0
    show_change_link = True
    autocomplete_fields = ["character"]


@admin.register(PlaySession)
class PlaySessionAdmin(admin.ModelAdmin):
    list_display = ["id", "club", "title", "starts_at", "game_master", "cancelled"]
    list_filter = ["cancelled", "club"]
    search_fields = ["title", "club__name", "location"]
    autocomplete_fields = ["club", "game_master"]
    list_select_related = ["club", "game_master__user"]
    readonly_fields = ["created", "updated"]
    inlines = [PlayerRSVPInline, SessionAttendanceInline, SessionAwardInline]
    fieldsets = (
        ("Main", {"fields": ("club", "title", "game_master", "cancelled")}),
        ("Schedule", {"fields": ("starts_at", "ends_at", "location", "created", "updated")}),
        ("Notes", {"fields": ("notes", "recap", "gm_notes"), "classes": ("collapse",)}),
    )


@admin.register(PlayerRSVP)
class PlayerRSVPAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "member", "answer", "answered_by", "answered_at"]
    list_filter = ["answer", "session__club"]
    search_fields = ["session__title", "member__user__email"]
    autocomplete_fields = ["session", "member", "answered_by"]
    list_select_related = ["session", "member__user", "answered_by"]
    readonly_fields = ["answered_at"]


@admin.register(AttendanceHint)
class AttendanceHintAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "character", "created"]
    list_filter = ["session__club"]
    search_fields = ["session__title", "character__name"]
    autocomplete_fields = ["session", "character"]
    list_select_related = ["session", "character"]
    readonly_fields = ["created"]


@admin.register(SessionAttendance)
class SessionAttendanceAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "character", "played", "confirmed_by", "confirmed_at"]
    list_filter = ["played", "session__club"]
    search_fields = ["session__title", "character__name"]
    autocomplete_fields = ["session", "character", "confirmed_by"]
    list_select_related = ["session", "character", "confirmed_by"]
    readonly_fields = ["confirmed_at"]


@admin.register(AttendanceChange)
class AttendanceChangeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "session",
        "character",
        "old_played",
        "new_played",
        "changed_by",
        "changed_at",
    ]
    list_filter = ["session__club"]
    search_fields = ["session__title", "character__name"]
    readonly_fields = [
        "session",
        "character",
        "old_played",
        "new_played",
        "changed_by",
        "changed_at",
    ]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SessionAward)
class SessionAwardAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "character", "points"]
    list_filter = ["session__club"]
    search_fields = ["session__title", "character__name"]
    autocomplete_fields = ["session", "character"]
    list_select_related = ["session", "character"]


@admin.register(SessionSettings)
class SessionSettingsAdmin(admin.ModelAdmin):
    list_display = ["club", "award_points", "feed_token"]
    search_fields = ["club__name"]
    autocomplete_fields = ["club"]
    list_select_related = ["club"]
