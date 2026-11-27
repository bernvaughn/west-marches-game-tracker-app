"""Admin editing theme for the map app.

Covers the new CreditGrant (read-only) and FoundMark admins plus the
editing-theme updates to HexMap, Tile, XPLevel, Location, Encounter,
LocationCredit, MapRequest and TileVisit.

For each model: GET the changelist, add form and change form as a
superuser (CreditGrant add is 403 because it is read-only). Assert the
configured FK widgets render in the change form
(admin-autocomplete for autocomplete_fields,
vForeignKeyRawIdAdminField for raw_id_fields). POST a valid change for
FoundMark and HexMap and assert it saves; POST LocationAdmin with its
inlines (management form TOTAL_FORMS=0). Assert run_checks() raises no
admin errors.

MapRequest.decided_by and decided_at are set by code when a request is
decided, so they are read-only in the admin and cannot be corrected by
hand.
"""

from datetime import date

import pytest
from django.contrib import admin
from django.core.checks import run_checks
from django.urls import reverse

from accounts.models import Membership, Message
from map.models import (
    CreditGrant,
    Encounter,
    FoundMark,
    HexMap,
    Location,
    LocationCredit,
    MapRequest,
    Tile,
    TileVisit,
    XPLevel,
)

pytestmark = pytest.mark.django_db

# (model, admin URL name, expected add-form status).
# CreditGrant is read-only, so its add form returns 403.
_ADMIN_MODELS = [
    (CreditGrant, "creditgrant", 403),
    (FoundMark, "foundmark", 200),
    (HexMap, "hexmap", 200),
    (Tile, "tile", 200),
    (XPLevel, "xplevel", 200),
    (Location, "location", 200),
    (Encounter, "encounter", 200),
    (LocationCredit, "locationcredit", 200),
    (MapRequest, "maprequest", 200),
    (TileVisit, "tilevisit", 200),
]


def _make_message(club, player):
    membership = Membership.objects.get(user=player, club=club)
    return Message.objects.create(club=club, sender=membership, body="Test")


def _instance(model_name, club, hex_map, tile_location, character, player):
    if model_name == "creditgrant":
        credit = LocationCredit.objects.create(
            location=tile_location, kind="discovered", date="2024-01-01"
        )
        return CreditGrant.objects.create(
            credit=credit, character=character, source_message=_make_message(club, player)
        )
    if model_name == "foundmark":
        return FoundMark.objects.create(location=tile_location, character=character)
    if model_name == "hexmap":
        return HexMap.objects.create(club=club, name="Old Name")
    if model_name == "tile":
        return Tile.objects.create(map=hex_map, q=3, r=3)
    if model_name == "xplevel":
        return XPLevel.objects.get_or_create(
            club=club, band="1-2", defaults={"discover_xp": 0, "explore_xp": 0}
        )[0]
    if model_name == "location":
        tile = Tile.objects.create(map=hex_map, q=9, r=9)
        return Location.objects.create(tile=tile, name="Watchtower")
    if model_name == "encounter":
        return Encounter.objects.create(
            location=tile_location, date="2024-01-15", description="Test"
        )
    if model_name == "locationcredit":
        return LocationCredit.objects.create(
            location=tile_location, kind="discovered", date="2024-01-15"
        )
    if model_name == "maprequest":
        membership = Membership.objects.get(user=player, club=club)
        return MapRequest.objects.create(
            club=club, kind="visit", status="requested", requested_by=membership
        )
    if model_name == "tilevisit":
        return TileVisit.objects.create(map=hex_map, q=4, r=4, character=character)
    raise ValueError(model_name)


@pytest.mark.parametrize("model,url_name,add_status", _ADMIN_MODELS)
def test_admin_pages(
    model,
    url_name,
    add_status,
    login,
    site_admin,
    club,
    hex_map,
    tile_location,
    character,
    player,
):
    """Changelist, add form and change form load for every map admin."""
    client = login(site_admin)
    instance = _instance(url_name, club, hex_map, tile_location, character, player)

    assert client.get(reverse(f"admin:map_{url_name}_changelist")).status_code == 200
    assert client.get(reverse(f"admin:map_{url_name}_add")).status_code == add_status
    assert (
        client.get(reverse(f"admin:map_{url_name}_change", args=[instance.pk])).status_code == 200
    )


@pytest.mark.parametrize("model,url_name,add_status", _ADMIN_MODELS)
def test_admin_fk_widgets(
    model,
    url_name,
    add_status,
    login,
    site_admin,
    club,
    hex_map,
    tile_location,
    character,
    player,
):
    """Declared autocomplete/raw_id FK widgets render on the change form."""
    client = login(site_admin)
    instance = _instance(url_name, club, hex_map, tile_location, character, player)
    model_admin = admin.site._registry[model]

    response = client.get(reverse(f"admin:map_{url_name}_change", args=[instance.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    for field in model_admin.autocomplete_fields:
        assert f'data-field-name="{field}"' in content
        assert "admin-autocomplete" in content
    for _field in model_admin.raw_id_fields:
        assert "vForeignKeyRawIdAdminField" in content


def test_maprequest_decided_stamps_are_readonly(
    login, site_admin, club, hex_map, tile_location, character, player
):
    """decided_by/decided_at are set by code, so they are read-only fields."""
    membership = Membership.objects.get(user=player, club=club)
    map_request = MapRequest.objects.create(
        club=club, kind="visit", status="requested", requested_by=membership
    )
    client = login(site_admin)
    response = client.get(reverse("admin:map_maprequest_change", args=[map_request.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="decided_by"' not in content
    assert 'name="decided_at"' not in content
    model_admin = admin.site._registry[MapRequest]
    assert model_admin.readonly_fields == ["decided_by", "decided_at"]


def test_foundmark_admin_change_saves(
    login, site_admin, club, hex_map, tile_location, character, player
):
    """POSTing a valid FoundMark change saves the new date."""
    found_mark = FoundMark.objects.create(location=tile_location, character=character)
    membership = Membership.objects.get(user=player, club=club)
    client = login(site_admin)
    url = reverse("admin:map_foundmark_change", args=[found_mark.pk])
    response = client.post(
        url,
        {
            "location": tile_location.pk,
            "character": character.pk,
            "date": "2024-03-20",
            "created_by": membership.pk,
            "source_message": "",
        },
    )
    assert response.status_code == 302
    found_mark.refresh_from_db()
    assert found_mark.date == date(2024, 3, 20)


def test_hexmap_admin_change_saves(login, site_admin, club):
    """POSTing a valid HexMap change saves the new name."""
    hex_map = HexMap.objects.create(club=club, name="Old Name")
    client = login(site_admin)
    response = client.post(
        reverse("admin:map_hexmap_change", args=[hex_map.pk]),
        {"name": "Renamed Map", "club": club.pk},
    )
    assert response.status_code == 302
    hex_map.refresh_from_db()
    assert hex_map.name == "Renamed Map"


def test_location_admin_change_saves_with_inlines(
    login, site_admin, tile_location, hex_map, character
):
    """POSTing a Location change with empty inline formsets saves."""
    client = login(site_admin)
    data = {
        "name": "Renamed Watchtower",
        "tile": tile_location.tile.pk,
        "encounters-TOTAL_FORMS": "0",
        "encounters-INITIAL_FORMS": "0",
        "encounters-MIN_NUM_FORMS": "0",
        "encounters-MAX_NUM_FORMS": "1000",
        "credits-TOTAL_FORMS": "0",
        "credits-INITIAL_FORMS": "0",
        "credits-MIN_NUM_FORMS": "0",
        "credits-MAX_NUM_FORMS": "1000",
    }
    response = client.post(reverse("admin:map_location_change", args=[tile_location.pk]), data)
    assert response.status_code == 302
    tile_location.refresh_from_db()
    assert tile_location.name == "Renamed Watchtower"


def test_admin_checks_have_no_errors():
    """django.core.checks.run_checks() reports no admin errors."""
    errors = [error for error in run_checks() if error.id.startswith("admin.")]
    assert not errors, [str(error) for error in errors]
