import datetime

import pytest

from map.models import LocationCredit, Tile, TileVisit
from map.services import (
    add_to_credit,
    ensure_tile,
    prune_tile,
    record_visits,
    remove_from_credit,
)

pytestmark = pytest.mark.story("MAP_CONTRACT")


def test_record_visits_idempotent(hex_map, player_character, second_character):
    first = record_visits(hex_map, 1, 1, [player_character, second_character])
    assert len(first) == 2
    assert first[0].date == datetime.date.today()
    assert record_visits(hex_map, 1, 1, [player_character]) == []
    assert TileVisit.objects.count() == 2


def test_record_visits_explicit_date(hex_map, player_character):
    d = datetime.date(2024, 1, 2)
    (visit,) = record_visits(hex_map, 1, 1, [player_character], d)
    assert visit.date == d


def test_add_to_credit_records_visits(tile_location, hex_map, player_character):
    add_to_credit(tile_location, "discovered", [player_character])
    credit = LocationCredit.objects.get(location=tile_location, kind="discovered")
    assert list(credit.characters.all()) == [player_character]
    assert TileVisit.objects.filter(map=hex_map, q=1, r=0, character=player_character).exists()


def test_remove_from_credit(tile_location, hex_map, player_character, second_character):
    add_to_credit(tile_location, "explored", [player_character, second_character])
    remove_from_credit(tile_location, "explored", [player_character])
    assert LocationCredit.objects.filter(location=tile_location).exists()
    remove_from_credit(tile_location, "explored", [second_character])
    assert not LocationCredit.objects.filter(location=tile_location).exists()
    assert TileVisit.objects.count() == 2
    remove_from_credit(tile_location, "explored", [second_character])


def test_ensure_and_prune(hex_map, tile_location):
    tile = ensure_tile(hex_map, 5, 5)
    assert ensure_tile(hex_map, 5, 5) == tile
    assert prune_tile(tile) is True
    assert not Tile.objects.filter(pk=tile.pk).exists()
    assert prune_tile(tile_location.tile) is False


def test_safe_town_never_pruned(hex_map):
    town = Tile.objects.get(map=hex_map, q=0, r=0)
    assert prune_tile(town) is False
    assert Tile.objects.filter(pk=town.pk).exists()
