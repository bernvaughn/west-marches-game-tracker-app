from django.contrib import admin

from .models import (
    Encounter,
    HexMap,
    Location,
    LocationCredit,
    MapRequest,
    Tile,
    TileVisit,
    XPLevel,
)


@admin.register(HexMap)
class HexMapAdmin(admin.ModelAdmin):
    list_display = ["name", "club", "archived"]
    list_filter = ["club", "archived"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(Tile)
class TileAdmin(admin.ModelAdmin):
    list_display = ["map", "q", "r", "is_safe_town"]
    list_filter = ["map__club", "is_safe_town"]
    search_fields = ["map__name"]
    ordering = ["map", "q", "r"]


@admin.register(XPLevel)
class XPLevelAdmin(admin.ModelAdmin):
    list_display = ["band", "club"]
    list_filter = ["club", "band"]
    search_fields = ["band"]
    ordering = ["club", "band"]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "tile"]
    list_filter = ["tile__map__club"]
    search_fields = ["name", "player_notes", "gm_notes"]
    ordering = ["name"]


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ["location", "date"]
    list_filter = ["location__tile__map__club"]
    search_fields = ["location__name", "description"]
    date_hierarchy = "date"
    ordering = ["-date"]


@admin.register(LocationCredit)
class LocationCreditAdmin(admin.ModelAdmin):
    list_display = ["location", "kind", "date"]
    list_filter = ["location__tile__map__club", "kind"]
    search_fields = ["location__name"]
    date_hierarchy = "date"
    ordering = ["-date"]


@admin.register(MapRequest)
class MapRequestAdmin(admin.ModelAdmin):
    list_display = ["kind", "club", "status", "created", "requested_by"]
    list_filter = ["club", "kind", "status"]
    search_fields = ["requested_by__user__email", "note"]
    date_hierarchy = "created"
    ordering = ["-created"]


@admin.register(TileVisit)
class TileVisitAdmin(admin.ModelAdmin):
    list_display = ["character", "map", "q", "r", "date"]
    list_filter = ["map__club"]
    search_fields = ["character__name"]
    ordering = ["map", "q", "r"]
