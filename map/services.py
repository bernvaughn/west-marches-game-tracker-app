from django.db import transaction
from django.utils import timezone

from .models import CreditGrant, FoundMark, LocationCredit, Tile, TileVisit


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
