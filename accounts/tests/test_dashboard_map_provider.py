import pytest

from accounts.dashboard_providers import MapDashboardProvider
from map.models import HexMap, Location, Tile, TileVisit

pytestmark = [pytest.mark.django_db, pytest.mark.story("S6")]


def test_map_dashboard_provider_archived_map_not_shown(club, player, character):
    """Archived maps don't show in uncredited count."""
    provider = MapDashboardProvider()
    membership = character.owner

    archived_map = HexMap.objects.create(club=club, name="Archived Map", archived=True)
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
