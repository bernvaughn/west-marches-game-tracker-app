from django.contrib import admin

from .models import (
    CreditGrant,
    Encounter,
    FoundMark,
    HexMap,
    Location,
    LocationCredit,
    MapRequest,
    Tile,
    TileVisit,
    XPLevel,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Read-only log admin: no add, change or delete."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class EncounterInline(admin.TabularInline):
    model = Encounter
    extra = 0
    show_change_link = True


class LocationCreditInline(admin.TabularInline):
    model = LocationCredit
    extra = 0
    show_change_link = True
    autocomplete_fields = ["characters"]


@admin.register(HexMap)
class HexMapAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "archived"]
    list_filter = ["club", "archived"]
    search_fields = ["name"]
    ordering = ["name"]
    autocomplete_fields = ["club"]
    list_select_related = ["club"]


@admin.register(Tile)
class TileAdmin(admin.ModelAdmin):
    list_display = ["map", "q", "r", "is_safe_town"]
    list_filter = ["map__club", "is_safe_town"]
    search_fields = ["map__name"]
    ordering = ["map", "q", "r"]
    autocomplete_fields = ["map"]
    list_select_related = ["map"]


@admin.register(XPLevel)
class XPLevelAdmin(admin.ModelAdmin):
    list_display = ["band", "club"]
    list_filter = ["club", "band"]
    search_fields = ["band"]
    ordering = ["club", "band"]
    autocomplete_fields = ["club"]
    list_select_related = ["club"]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "tile"]
    list_filter = ["tile__map__club"]
    search_fields = ["name", "player_notes", "gm_notes"]
    ordering = ["name"]
    autocomplete_fields = ["tile"]
    list_select_related = ["tile__map"]
    inlines = [EncounterInline, LocationCreditInline]


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ["location", "date"]
    list_filter = ["location__tile__map__club"]
    search_fields = ["location__name", "description"]
    date_hierarchy = "date"
    ordering = ["-date"]
    autocomplete_fields = ["location"]
    list_select_related = ["location"]


@admin.register(LocationCredit)
class LocationCreditAdmin(admin.ModelAdmin):
    list_display = ["location", "kind", "date"]
    list_filter = ["location__tile__map__club", "kind"]
    search_fields = ["location__name"]
    date_hierarchy = "date"
    ordering = ["-date"]
    autocomplete_fields = ["location", "characters"]
    list_select_related = ["location"]


@admin.register(CreditGrant)
class CreditGrantAdmin(ReadOnlyAdmin):
    """Log-style read-only admin for inbox credit grants."""

    list_display = ["credit", "character", "source_message", "created"]
    list_filter = ["credit__location__tile__map__club"]
    search_fields = ["character__name", "credit__location__name"]
    date_hierarchy = "created"
    ordering = ["-created"]
    list_select_related = ["credit__location", "character", "source_message"]


@admin.register(FoundMark)
class FoundMarkAdmin(admin.ModelAdmin):
    list_display = ["location", "character", "date", "created_by"]
    list_filter = ["location__tile__map__club"]
    search_fields = ["character__name", "location__name"]
    date_hierarchy = "date"
    autocomplete_fields = ["location", "character", "created_by"]
    raw_id_fields = ["source_message"]
    list_select_related = ["location", "character", "created_by__user"]


@admin.register(MapRequest)
class MapRequestAdmin(admin.ModelAdmin):
    list_display = ["kind", "club", "status", "created", "requested_by"]
    list_filter = ["club", "kind", "status"]
    search_fields = ["requested_by__user__email", "note"]
    date_hierarchy = "created"
    ordering = ["-created"]
    autocomplete_fields = ["club", "requested_by", "tile", "location", "map", "characters"]
    readonly_fields = ["decided_by", "decided_at"]
    list_select_related = ["club", "requested_by__user"]
    fieldsets = [
        (
            "Main",
            {
                "fields": [
                    "club",
                    "kind",
                    "status",
                    "date",
                    "characters",
                    "requested_by",
                    "tile",
                    "location",
                    "map",
                    "q",
                    "r",
                    "note",
                ],
            },
        ),
        (
            "Decision",
            {
                "classes": ["collapse"],
                "fields": ["decided_by", "decided_at"],
            },
        ),
    ]


@admin.register(TileVisit)
class TileVisitAdmin(admin.ModelAdmin):
    list_display = ["character", "map", "q", "r", "date"]
    list_filter = ["map__club"]
    search_fields = ["character__name"]
    ordering = ["map", "q", "r"]
    autocomplete_fields = ["map", "character"]
    raw_id_fields = ["source_message"]
    list_select_related = ["map", "character"]
