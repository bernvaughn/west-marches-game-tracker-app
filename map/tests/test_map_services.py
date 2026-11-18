import pytest

from map.models import FoundMark, HexMap, Location, LocationCredit, Tile, TileVisit
from map.services import UncreditedTilesResult, get_uncredited_tiles

pytestmark = [pytest.mark.django_db, pytest.mark.story("MAP_CONTRACT")]


def test_get_uncredited_tiles_no_visits_returns_empty(club, player, character):
    """Returns empty result when character has no tile visits."""
    HexMap.objects.create(club=club, name="Test Map")

    result = get_uncredited_tiles(club, character)

    assert isinstance(result, UncreditedTilesResult)
    assert result.maps_data == []
    assert result.total_uncredited == 0
    assert result.first_map is None
    assert result.first_map_uncredited_tiles is None


def test_get_uncredited_tiles_visits_no_locations_returns_empty(club, player, character):
    """Returns empty result when character has visits but no locations on visited tiles."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    Tile.objects.create(map=hex_map, q=1, r=0)

    result = get_uncredited_tiles(club, character)

    assert result.maps_data == []
    assert result.total_uncredited == 0
    assert result.first_map is None
    assert result.first_map_uncredited_tiles is None


def test_get_uncredited_tiles_visits_with_full_credit_returns_empty(club, player, character):
    """Returns empty result when character has full credit for all visited locations."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(tile=tile, name="Test Location")

    # Give full credit (discovered, explored, found)
    dc = LocationCredit.objects.create(location=location, kind=LocationCredit.Kind.DISCOVERED)
    dc.characters.add(character)
    ec = LocationCredit.objects.create(location=location, kind=LocationCredit.Kind.EXPLORED)
    ec.characters.add(character)
    FoundMark.objects.create(location=location, character=character)

    result = get_uncredited_tiles(club, character)

    assert result.maps_data == []
    assert result.total_uncredited == 0
    assert result.first_map is None
    assert result.first_map_uncredited_tiles is None


def test_get_uncredited_tiles_missing_discovered_returns_uncredited(club, player, character):
    """Returns uncredited tiles when character is missing discovered credit."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(tile=tile, name="Test Location")

    # Only explored and found credit, missing discovered
    ec = LocationCredit.objects.create(location=location, kind=LocationCredit.Kind.EXPLORED)
    ec.characters.add(character)
    FoundMark.objects.create(location=location, character=character)

    result = get_uncredited_tiles(club, character)

    assert len(result.maps_data) == 1
    assert result.maps_data[0]["map"] == hex_map
    assert result.maps_data[0]["uncredited_count"] == 1
    assert result.total_uncredited == 1
    assert result.first_map == hex_map
    assert result.first_map_uncredited_tiles == {(1, 0)}


def test_get_uncredited_tiles_missing_explored_returns_uncredited(club, player, character):
    """Returns uncredited tiles when character is missing explored credit."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(tile=tile, name="Test Location")

    # Only discovered and found credit, missing explored
    dc = LocationCredit.objects.create(location=location, kind=LocationCredit.Kind.DISCOVERED)
    dc.characters.add(character)
    FoundMark.objects.create(location=location, character=character)

    result = get_uncredited_tiles(club, character)

    assert result.total_uncredited == 1
    assert result.first_map == hex_map
    assert result.first_map_uncredited_tiles == {(1, 0)}


def test_get_uncredited_tiles_missing_found_returns_uncredited(club, player, character):
    """Returns uncredited tiles when character is missing found mark."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(tile=tile, name="Test Location")

    # Only discovered and explored credit, missing found
    dc = LocationCredit.objects.create(location=location, kind=LocationCredit.Kind.DISCOVERED)
    dc.characters.add(character)
    ec = LocationCredit.objects.create(location=location, kind=LocationCredit.Kind.EXPLORED)
    ec.characters.add(character)

    result = get_uncredited_tiles(club, character)

    assert result.total_uncredited == 1
    assert result.first_map == hex_map
    assert result.first_map_uncredited_tiles == {(1, 0)}


def test_get_uncredited_tiles_get_context_count(club, player, character):
    """Returns correct total_uncredited count for multiple tiles."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    TileVisit.objects.create(map=hex_map, q=2, r=0, character=character)

    # Two tiles with locations, both missing credit
    tile1 = Tile.objects.create(map=hex_map, q=1, r=0)
    tile2 = Tile.objects.create(map=hex_map, q=2, r=0)
    Location.objects.create(tile=tile1, name="Location 1")
    Location.objects.create(tile=tile2, name="Location 2")

    result = get_uncredited_tiles(club, character)

    assert result.total_uncredited == 2
    assert result.first_map == hex_map
    assert result.first_map_uncredited_tiles == {(1, 0), (2, 0)}


def test_get_uncredited_tiles_multiple_maps_first_map_used(club, player, character):
    """First map alphabetically is used for first_map."""
    map1 = HexMap.objects.create(club=club, name="Map A")
    map2 = HexMap.objects.create(club=club, name="Map B")

    # Visit on map1 with uncredited location
    TileVisit.objects.create(map=map1, q=1, r=0, character=character)
    tile1 = Tile.objects.create(map=map1, q=1, r=0)
    Location.objects.create(tile=tile1, name="Location A")

    # Visit on map2 with uncredited location
    TileVisit.objects.create(map=map2, q=1, r=0, character=character)
    tile2 = Tile.objects.create(map=map2, q=1, r=0)
    Location.objects.create(tile=tile2, name="Location B")

    result = get_uncredited_tiles(club, character)

    assert result.total_uncredited == 2
    assert result.first_map == map1  # Map A comes first alphabetically
    assert result.first_map_uncredited_tiles == {(1, 0)}
    assert len(result.maps_data) == 2
    # Maps data should be ordered by name
    assert result.maps_data[0]["map"] == map1
    assert result.maps_data[1]["map"] == map2


def test_get_uncredited_tiles_archived_map_included_in_count(club, player, character):
    """Archived maps are included in uncredited count (matching original provider behavior)."""
    archived_map = HexMap.objects.create(club=club, name="Archived Map", archived=True)
    HexMap.objects.create(club=club, name="Active Map")

    TileVisit.objects.create(map=archived_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=archived_map, q=1, r=0)
    Location.objects.create(tile=tile, name="Location")

    result = get_uncredited_tiles(club, character)

    # Archived map should appear in maps_data (original behavior)
    assert len(result.maps_data) == 1
    assert result.maps_data[0]["map"] == archived_map
    assert result.total_uncredited == 1
    assert result.first_map == archived_map
    assert result.first_map_uncredited_tiles == {(1, 0)}


def test_get_uncredited_tiles_multiple_locations_same_tile_counted_once(club, player, character):
    """Multiple locations on same tile count as one uncredited tile."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)

    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    Location.objects.create(tile=tile, name="Location 1")
    Location.objects.create(tile=tile, name="Location 2")
    Location.objects.create(tile=tile, name="Location 3")

    result = get_uncredited_tiles(club, character)

    # All three locations on same tile, should count as 1 uncredited tile
    assert result.total_uncredited == 1
    assert result.first_map_uncredited_tiles == {(1, 0)}


def test_get_uncredited_tiles_partial_credit_on_multiple_tiles(club, player, character):
    """Multiple tiles with varying credit levels."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")

    # Tile 1: full credit
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile1 = Tile.objects.create(map=hex_map, q=1, r=0)
    loc1 = Location.objects.create(tile=tile1, name="Location 1")
    dc1 = LocationCredit.objects.create(location=loc1, kind=LocationCredit.Kind.DISCOVERED)
    dc1.characters.add(character)
    ec1 = LocationCredit.objects.create(location=loc1, kind=LocationCredit.Kind.EXPLORED)
    ec1.characters.add(character)
    FoundMark.objects.create(location=loc1, character=character)

    # Tile 2: missing discovered
    TileVisit.objects.create(map=hex_map, q=2, r=0, character=character)
    tile2 = Tile.objects.create(map=hex_map, q=2, r=0)
    loc2 = Location.objects.create(tile=tile2, name="Location 2")
    ec2 = LocationCredit.objects.create(location=loc2, kind=LocationCredit.Kind.EXPLORED)
    ec2.characters.add(character)
    FoundMark.objects.create(location=loc2, character=character)

    # Tile 3: no credit at all
    TileVisit.objects.create(map=hex_map, q=3, r=0, character=character)
    tile3 = Tile.objects.create(map=hex_map, q=3, r=0)
    Location.objects.create(tile=tile3, name="Location 3")

    result = get_uncredited_tiles(club, character)

    # Only tiles 2 and 3 should be uncredited
    assert result.total_uncredited == 2
    assert result.first_map_uncredited_tiles == {(2, 0), (3, 0)}
    assert result.maps_data[0]["uncredited_count"] == 2


def test_get_uncredited_tiles_different_characters_isolated(
    club, player, character, second_character
):
    """Uncredited tiles are computed per character."""
    hex_map = HexMap.objects.create(club=club, name="Test Map")

    # Character 1 has visit and location
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    Location.objects.create(tile=tile, name="Location 1")

    # Character 2 has visit but no location
    TileVisit.objects.create(map=hex_map, q=2, r=0, character=second_character)
    Tile.objects.create(map=hex_map, q=2, r=0)

    result_char1 = get_uncredited_tiles(club, character)
    result_char2 = get_uncredited_tiles(club, second_character)

    assert result_char1.total_uncredited == 1
    assert result_char2.total_uncredited == 0
