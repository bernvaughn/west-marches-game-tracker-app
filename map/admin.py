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

admin.site.register(
    [HexMap, Tile, XPLevel, Location, Encounter, LocationCredit, MapRequest, TileVisit]
)
