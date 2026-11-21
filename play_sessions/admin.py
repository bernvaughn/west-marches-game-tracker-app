from django.contrib import admin

from .models import (
    AttendanceChange,
    PlaySession,
    SessionAttendance,
    SessionAward,
    SessionRSVP,
    SessionSeries,
    SessionSettings,
)


@admin.register(SessionSeries)
class SessionSeriesAdmin(admin.ModelAdmin):
    list_display = ["id", "club", "rule", "created_by", "created"]
    list_filter = ["rule", "club"]
    search_fields = ["club__name"]
    readonly_fields = ["created"]


@admin.register(PlaySession)
class PlaySessionAdmin(admin.ModelAdmin):
    list_display = ["id", "club", "title", "starts_at", "game_master", "cancelled"]
    list_filter = ["cancelled", "club"]
    search_fields = ["title", "club__name", "location"]
    readonly_fields = ["created", "updated"]


@admin.register(SessionRSVP)
class SessionRSVPAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "character", "answer", "answered_by", "answered_at"]
    list_filter = ["answer", "session__club"]
    search_fields = ["session__title", "character__name"]
    readonly_fields = ["answered_at"]


@admin.register(SessionAttendance)
class SessionAttendanceAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "character", "played", "confirmed_by", "confirmed_at"]
    list_filter = ["played", "session__club"]
    search_fields = ["session__title", "character__name"]
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


@admin.register(SessionSettings)
class SessionSettingsAdmin(admin.ModelAdmin):
    list_display = ["club", "award_points", "feed_token"]
    search_fields = ["club__name"]
