from django.utils import timezone

from accounts.models import Membership
from player_characters.models import Character

from .models import Encounter, HexMap, Location, LocationCredit, MapRequest, Tile, TileVisit
from .xp import copy_default_xp_table

LOCATIONS = [
    (1, 0, "Old Watchtower", "1-2"),
    (0, -2, "Wolf Den", "3-4"),
    (-2, 1, "Sunken Shrine", "5-6"),
]
VISITS = {
    "Aria Windrunner": [(0, 0), (1, 0), (0, -2)],
    "Borin Stonefist": [(0, 0), (1, 0)],
}


def seed(club):
    copy_default_xp_table(club)
    hex_map = HexMap.objects.filter(club=club, name="The Marches").first()
    if hex_map is None:
        hex_map = HexMap.objects.create(club=club, name="The Marches")
    locations = {}
    for q, r, name, band in LOCATIONS:
        tile, _ = Tile.objects.get_or_create(map=hex_map, q=q, r=r)
        locations[name], _ = Location.objects.get_or_create(
            tile=tile, name=name, defaults={"target_band": band}
        )
    wolf_den = locations["Wolf Den"]
    if not wolf_den.encounters.exists():
        Encounter.objects.create(location=wolf_den, description="A pack of wolves.")
    today = timezone.localdate()
    chars = {c.name: c for c in Character.objects.filter(club=club)}
    for name, tiles in VISITS.items():
        for q, r in tiles:
            TileVisit.objects.get_or_create(
                map=hex_map, q=q, r=r, character=chars[name], defaults={"date": today}
            )
    credit, created = LocationCredit.objects.get_or_create(
        location=locations["Old Watchtower"],
        kind=LocationCredit.Kind.DISCOVERED,
        defaults={"date": today},
    )
    if created:
        credit.characters.add(chars["Aria Windrunner"])

    borin = chars["Borin Stonefist"]
    owner = Membership.objects.filter(pk=borin.owner_id).first()
    if (
        owner is not None
        and not MapRequest.objects.filter(
            club=club, kind=MapRequest.Kind.VISIT, map=hex_map, q=0, r=-2, requested_by=owner
        ).exists()
    ):
        req = MapRequest.objects.create(
            club=club,
            kind=MapRequest.Kind.VISIT,
            map=hex_map,
            q=0,
            r=-2,
            date=today,
            note="We passed the Wolf Den on the way back.",
            requested_by=owner,
        )
        req.characters.add(borin)
