from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import CreditGrant, FoundMark, HexMap, Location, LocationCredit, Tile, TileVisit


@transaction.atomic
def ensure_tile(hex_map, q, r):
    tile, _ = Tile.objects.get_or_create(map=hex_map, q=q, r=r)
    return tile


@transaction.atomic
def prune_tile(tile):
    if tile.is_safe_town or tile.locations.exists():
        return False
    tile.delete()
    return True


@transaction.atomic
def record_visits(hex_map, q, r, characters, date=None, source_message=None):
    date = date or timezone.localdate()
    created = []
    for character in characters:
        visit, was_created = TileVisit.objects.get_or_create(
            map=hex_map,
            q=q,
            r=r,
            character=character,
            defaults={"date": date, "source_message": source_message},
        )
        if was_created:
            created.append(visit)
    return created


@transaction.atomic
def add_to_credit(location, kind, characters, date=None, source_message=None):
    characters = list(characters)
    date = date or timezone.localdate()
    credit, _ = LocationCredit.objects.get_or_create(
        location=location, kind=kind, defaults={"date": date}
    )
    existing = set(credit.characters.filter(pk__in=[c.pk for c in characters]))
    credit.characters.add(*characters)
    if source_message is not None:
        for character in characters:
            if character not in existing:
                CreditGrant.objects.get_or_create(
                    credit=credit, character=character, source_message=source_message
                )
    tile = location.tile
    record_visits(tile.map, tile.q, tile.r, characters, date, source_message)
    return credit


@transaction.atomic
def remove_from_credit(location, kind, characters):
    credit = LocationCredit.objects.filter(location=location, kind=kind).first()
    if credit is None:
        return
    credit.characters.remove(*list(characters))
    if not credit.characters.exists():
        credit.delete()


@transaction.atomic
def add_found_marks(location, characters, date=None, created_by=None, source_message=None):
    characters = list(characters)
    date = date or timezone.localdate()
    created = []
    for character in characters:
        mark, was_created = FoundMark.objects.get_or_create(
            location=location,
            character=character,
            defaults={"date": date, "created_by": created_by, "source_message": source_message},
        )
        if was_created:
            created.append(mark)
    tile = location.tile
    record_visits(tile.map, tile.q, tile.r, characters, date, source_message)
    return created


@transaction.atomic
def remove_found_marks(location, characters):
    FoundMark.objects.filter(location=location, character__in=list(characters)).delete()


@dataclass
class UncreditedTilesResult:
    """Structured result for uncredited tiles query."""

    maps_data: list[dict]
    total_uncredited: int
    first_map: HexMap | None
    first_map_uncredited_tiles: set[tuple[int, int]] | None


def get_uncredited_tiles(club, character) -> UncreditedTilesResult:
    """Get maps with uncredited tiles for a character.

    Returns an UncreditedTilesResult with:
    - maps_data: list of dicts with 'map' (HexMap) and 'uncredited_count' (int)
    - total_uncredited: total count of unique uncredited tiles across all maps
    - first_map: first HexMap with uncredited tiles (alphabetically by name)
    - first_map_uncredited_tiles: set of (q, r) tuples for uncredited tiles on first_map
    """
    # Get all tile visits for this character
    visits = TileVisit.objects.for_club(club).filter(character=character).select_related("map")

    # Group visits by map
    map_visits = {}
    for visit in visits:
        if visit.map_id not in map_visits:
            map_visits[visit.map_id] = []
        map_visits[visit.map_id].append((visit.q, visit.r))

    if not map_visits:
        return UncreditedTilesResult([], 0, None, None)

    # Get maps with visits
    maps_with_visits = (
        HexMap.objects.for_club(club).filter(pk__in=map_visits.keys()).order_by("name")
    )

    maps_data = []
    total_uncredited = 0
    first_map = None
    first_map_uncredited_tiles = None

    for hex_map in maps_with_visits:
        visited_positions = set(map_visits[hex_map.pk])

        # Get locations on visited tiles
        locations = (
            Location.objects.for_club(club)
            .filter(
                tile__map=hex_map,
                tile__q__in=[q for q, r in visited_positions],
                tile__r__in=[r for q, r in visited_positions],
            )
            .select_related("tile")
        )

        # Check each location for missing credits
        map_uncredited_tiles = set()
        for loc in locations:
            pos = (loc.tile.q, loc.tile.r)
            if pos not in visited_positions:
                continue

            # Check if character has credit for this location
            has_discovered = (
                LocationCredit.objects.for_club(club)
                .filter(location=loc, kind=LocationCredit.Kind.DISCOVERED, characters=character)
                .exists()
            )

            has_explored = (
                LocationCredit.objects.for_club(club)
                .filter(location=loc, kind=LocationCredit.Kind.EXPLORED, characters=character)
                .exists()
            )

            has_found = (
                FoundMark.objects.for_club(club).filter(location=loc, character=character).exists()
            )

            # If any credit type is missing, this tile needs credit
            if not (has_discovered and has_explored and has_found):
                map_uncredited_tiles.add(pos)

        uncredited_count = len(map_uncredited_tiles)
        if uncredited_count > 0:
            total_uncredited += uncredited_count
            maps_data.append(
                {
                    "map": hex_map,
                    "uncredited_count": uncredited_count,
                }
            )
            if first_map is None:
                first_map = hex_map
                first_map_uncredited_tiles = map_uncredited_tiles

    return UncreditedTilesResult(
        maps_data=maps_data,
        total_uncredited=total_uncredited,
        first_map=first_map,
        first_map_uncredited_tiles=first_map_uncredited_tiles,
    )
