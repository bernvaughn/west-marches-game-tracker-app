"""Tests for map admin list pages."""

import pytest
from django.urls import reverse

from accounts.models import Membership
from map.models import (
    Encounter,
    HexMap,
    LocationCredit,
    MapRequest,
    Tile,
    TileVisit,
    XPLevel,
)

pytestmark = pytest.mark.django_db


def test_hexmap_admin_changelist(login, site_admin):
    client = login(site_admin)
    url = reverse("admin:map_hexmap_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_hexmap_admin_change_form(login, site_admin, club):
    client = login(site_admin)
    hex_map = HexMap.objects.create(club=club, name="Test Map")
    url = reverse("admin:map_hexmap_change", args=[hex_map.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_tile_admin_changelist(login, site_admin):
    client = login(site_admin)
    url = reverse("admin:map_tile_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_tile_admin_change_form(login, site_admin, hex_map):
    client = login(site_admin)
    tile = Tile.objects.create(map=hex_map, q=1, r=1)
    url = reverse("admin:map_tile_change", args=[tile.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_xplevel_admin_changelist(login, site_admin):
    client = login(site_admin)
    url = reverse("admin:map_xplevel_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_xplevel_admin_change_form(login, site_admin, club):
    client = login(site_admin)
    # Use an existing XPLevel for the club (created by xp tests)
    xp_level = XPLevel.objects.filter(club=club).first()
    if not xp_level:
        xp_level = XPLevel.objects.create(club=club, band="1-2", discover_xp=100, explore_xp=200)
    url = reverse("admin:map_xplevel_change", args=[xp_level.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_location_admin_changelist(login, site_admin):
    client = login(site_admin)
    url = reverse("admin:map_location_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_location_admin_change_form(login, site_admin, tile_location):
    client = login(site_admin)
    url = reverse("admin:map_location_change", args=[tile_location.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_encounter_admin_changelist(login, site_admin):
    client = login(site_admin)
    url = reverse("admin:map_encounter_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_encounter_admin_change_form(login, site_admin, tile_location):
    client = login(site_admin)
    encounter = Encounter.objects.create(
        location=tile_location, date="2024-01-15", description="Test encounter"
    )
    url = reverse("admin:map_encounter_change", args=[encounter.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_locationcredit_admin_changelist(login, site_admin):
    client = login(site_admin)
    url = reverse("admin:map_locationcredit_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_locationcredit_admin_change_form(login, site_admin, tile_location):
    client = login(site_admin)
    credit = LocationCredit.objects.create(
        location=tile_location, kind="discovered", date="2024-01-15"
    )
    url = reverse("admin:map_locationcredit_change", args=[credit.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_maprequest_admin_changelist(login, site_admin):
    client = login(site_admin)
    url = reverse("admin:map_maprequest_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_maprequest_admin_change_form(login, site_admin, club, player):
    client = login(site_admin)
    membership = Membership.objects.get(user=player, club=club)
    map_request = MapRequest.objects.create(
        club=club,
        kind="visit",
        status="requested",
        requested_by=membership,
    )
    url = reverse("admin:map_maprequest_change", args=[map_request.pk])
    response = client.get(url)
    assert response.status_code == 200


def test_tilevisit_admin_changelist(login, site_admin):
    client = login(site_admin)
    url = reverse("admin:map_tilevisit_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_tilevisit_admin_change_form(login, site_admin, hex_map, character):
    client = login(site_admin)
    tile_visit = TileVisit.objects.create(
        map=hex_map, q=2, r=2, character=character, date="2024-01-15"
    )
    url = reverse("admin:map_tilevisit_change", args=[tile_visit.pk])
    response = client.get(url)
    assert response.status_code == 200
