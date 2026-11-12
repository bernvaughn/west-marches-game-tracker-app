from django.db import transaction
from django.utils import timezone

from .models import FoundMark, LocationCredit, Tile, TileVisit


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
def record_visits(hex_map, q, r, characters, date=None):
    date = date or timezone.localdate()
    created = []
    for character in characters:
        visit, was_created = TileVisit.objects.get_or_create(
            map=hex_map, q=q, r=r, character=character, defaults={"date": date}
        )
        if was_created:
            created.append(visit)
    return created


@transaction.atomic
def add_to_credit(location, kind, characters, date=None):
    characters = list(characters)
    date = date or timezone.localdate()
    credit, _ = LocationCredit.objects.get_or_create(
        location=location, kind=kind, defaults={"date": date}
    )
    credit.characters.add(*characters)
    tile = location.tile
    record_visits(tile.map, tile.q, tile.r, characters, date)
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
def add_found_marks(location, characters, date=None, created_by=None):
    characters = list(characters)
    date = date or timezone.localdate()
    for character in characters:
        FoundMark.objects.get_or_create(
            location=location,
            character=character,
            defaults={"date": date, "created_by": created_by},
        )
    tile = location.tile
    record_visits(tile.map, tile.q, tile.r, characters, date)


@transaction.atomic
def remove_found_marks(location, characters):
    FoundMark.objects.filter(location=location, character__in=list(characters)).delete()
