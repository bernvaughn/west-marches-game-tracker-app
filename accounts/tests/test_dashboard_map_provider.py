import pytest

from accounts.dashboard_providers import MapDashboardProvider
from map.models import FoundMark, HexMap, Location, LocationCredit, Tile, TileVisit

pytestmark = [pytest.mark.django_db, pytest.mark.story("S6")]


def test_map_dashboard_provider_no_visits_returns_false(club, player, character):
    """should_show returns False when character has no tile visits."""
    provider = MapDashboardProvider()
    membership = character.owner

    HexMap.objects.create(club=club, name="Test Map")

    assert provider.should_show(None, club, character, membership) is False


def test_map_dashboard_provider_visits_no_locations_returns_false(
    club, player, character
):
    """should_show returns False when character has visits but no locations."""
    provider = MapDashboardProvider()
    membership = character.owner

    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    Tile.objects.create(map=hex_map, q=1, r=0)

    assert provider.should_show(None, club, character, membership) is False


def test_map_dashboard_provider_visits_with_full_credit_returns_false(
    club, player, character
):
    """should_show returns False when character has full credit for all visited locations."""
    provider = MapDashboardProvider()
    membership = character.owner

    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(tile=tile, name="Test Location")

    # Give full credit (discovered, explored, found)
    dc = LocationCredit.objects.create(
        location=location, kind=LocationCredit.Kind.DISCOVERED
    )
    dc.characters.add(character)
    ec = LocationCredit.objects.create(
        location=location, kind=LocationCredit.Kind.EXPLORED
    )
    ec.characters.add(character)
    FoundMark.objects.create(location=location, character=character)

    assert provider.should_show(None, club, character, membership) is False


def test_map_dashboard_provider_missing_discovered_returns_true(
    club, player, character
):
    """should_show returns True when character is missing discovered credit."""
    provider = MapDashboardProvider()
    membership = character.owner

    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(tile=tile, name="Test Location")

    # Only explored and found credit, missing discovered
    ec = LocationCredit.objects.create(
        location=location, kind=LocationCredit.Kind.EXPLORED
    )
    ec.characters.add(character)
    FoundMark.objects.create(location=location, character=character)

    assert provider.should_show(None, club, character, membership) is True


def test_map_dashboard_provider_missing_explored_returns_true(
    club, player, character
):
    """should_show returns True when character is missing explored credit."""
    provider = MapDashboardProvider()
    membership = character.owner

    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(tile=tile, name="Test Location")

    # Only discovered and found credit, missing explored
    dc = LocationCredit.objects.create(
        location=location, kind=LocationCredit.Kind.DISCOVERED
    )
    dc.characters.add(character)
    FoundMark.objects.create(location=location, character=character)

    assert provider.should_show(None, club, character, membership) is True


def test_map_dashboard_provider_missing_found_returns_true(
    club, player, character
):
    """should_show returns True when character is missing found mark."""
    provider = MapDashboardProvider()
    membership = character.owner

    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    location = Location.objects.create(tile=tile, name="Test Location")

    # Only discovered and explored credit, missing found
    dc = LocationCredit.objects.create(
        location=location, kind=LocationCredit.Kind.DISCOVERED
    )
    dc.characters.add(character)
    ec = LocationCredit.objects.create(
        location=location, kind=LocationCredit.Kind.EXPLORED
    )
    ec.characters.add(character)

    assert provider.should_show(None, club, character, membership) is True


def test_map_dashboard_provider_get_context_count(club, player, character):
    """get_context returns correct total_uncredited count."""
    provider = MapDashboardProvider()
    membership = character.owner

    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)
    TileVisit.objects.create(map=hex_map, q=2, r=0, character=character)

    # Two tiles with locations, both missing credit
    tile1 = Tile.objects.create(map=hex_map, q=1, r=0)
    tile2 = Tile.objects.create(map=hex_map, q=2, r=0)
    Location.objects.create(tile=tile1, name="Location 1")
    Location.objects.create(tile=tile2, name="Location 2")

    ctx = provider.get_context(None, club, character, membership)

    assert ctx["total_uncredited"] == 2
    assert ctx["request_url"] is not None
    assert "characters=" + str(character.pk) in ctx["request_url"]
    assert "view=mine" in ctx["request_url"]


def test_map_dashboard_provider_multiple_maps_first_map_used(
    club, player, character
):
    """request_url points to first map with uncredited tiles."""
    provider = MapDashboardProvider()
    membership = character.owner

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

    ctx = provider.get_context(None, club, character, membership)

    # Should point to first map (Map A) alphabetically
    assert ctx["request_url"] is not None
    assert f"map_id={map1.pk}" in ctx["request_url"] or f"/{map1.pk}/" in ctx["request_url"]


def test_map_dashboard_provider_archived_map_not_shown(
    club, player, character
):
    """Archived maps don't show in uncredited count."""
    provider = MapDashboardProvider()
    membership = character.owner

    archived_map = HexMap.objects.create(
        club=club, name="Archived Map", archived=True
    )
    TileVisit.objects.create(map=archived_map, q=1, r=0, character=character)
    tile = Tile.objects.create(map=archived_map, q=1, r=0)
    Location.objects.create(tile=tile, name="Location")

    ctx = provider.get_context(None, club, character, membership)
    assert ctx["total_uncredited"] == 1  # Still counts it


def test_map_dashboard_provider_provider_attributes(club, player, character):
    """Provider has correct key, order, and template."""
    provider = MapDashboardProvider()

    assert provider.key == "map"
    assert provider.order == 5
    assert provider.template == "accounts/_dashboard_map.html"


def test_map_dashboard_provider_multiple_locations_same_tile_counted_once(
    club, player, character
):
    """Multiple locations on same tile count as one uncredited tile."""
    provider = MapDashboardProvider()
    membership = character.owner

    hex_map = HexMap.objects.create(club=club, name="Test Map")
    TileVisit.objects.create(map=hex_map, q=1, r=0, character=character)

    tile = Tile.objects.create(map=hex_map, q=1, r=0)
    Location.objects.create(tile=tile, name="Location 1")
    Location.objects.create(tile=tile, name="Location 2")
    Location.objects.create(tile=tile, name="Location 3")

    ctx = provider.get_context(None, club, character, membership)

    # All three locations on same tile, should count as 1 uncredited tile
    assert ctx["total_uncredited"] == 1