"""Test starting_equipment admin editing: changelists, forms, FK widgets, and actions."""

import pytest
from django.contrib import admin as django_admin
from django.core import checks
from django.urls import reverse

from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentLevelCoins,
    StartingEquipmentRequest,
    StartingEquipmentTemplate,
)


def _get_model_admin(model_class):
    """Get the registered ModelAdmin instance for a model."""
    return django_admin.site._registry.get(model_class)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class,fixture_name,changelist_url",
    [
        (
            StartingEquipmentTemplate,
            "template",
            "admin:starting_equipment_startingequipmenttemplate_changelist",
        ),
        (
            StartingEquipmentClassEntry,
            "class_entry",
            "admin:starting_equipment_startingequipmentclassentry_changelist",
        ),
        (
            StartingEquipmentClassLine,
            "class_line",
            "admin:starting_equipment_startingequipmentclassline_changelist",
        ),
        (
            StartingEquipmentBackgroundEntry,
            "bg_entry",
            "admin:starting_equipment_startingequipmentbackgroundentry_changelist",
        ),
        (
            StartingEquipmentBackgroundLine,
            "bg_line",
            "admin:starting_equipment_startingequipmentbackgroundline_changelist",
        ),
        (
            StartingEquipmentLevelCoins,
            "level_coins",
            "admin:starting_equipment_startingequipmentlevelcoins_changelist",
        ),
        (
            MagicItemStartingOption,
            "magic_option",
            "admin:starting_equipment_magicitemstartingoption_changelist",
        ),
        (
            StartingEquipmentRequest,
            "pending_request",
            "admin:starting_equipment_startingequipmentrequest_changelist",
        ),
    ],
)
def test_starting_equipment_admin_changelist_and_forms(
    site_admin, login, request, model_class, fixture_name, changelist_url
):
    """All starting_equipment admins: changelist, add form, and change form load (200)."""
    obj = request.getfixturevalue(fixture_name)
    client = login(site_admin)

    # Changelist
    response = client.get(reverse(changelist_url))
    assert response.status_code == 200

    # Add form
    add_url = reverse(changelist_url.replace("_changelist", "_add"))
    response = client.get(add_url)
    assert response.status_code == 200

    # Change form
    change_url = reverse(changelist_url.replace("_changelist", "_change"), args=[obj.pk])
    response = client.get(change_url)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class,expected_autocomplete,expected_raw_id",
    [
        (StartingEquipmentTemplate, ("club",), ()),
        (StartingEquipmentClassEntry, ("template", "class_option"), ()),
        (StartingEquipmentClassLine, ("class_entry", "item"), ()),
        (StartingEquipmentBackgroundEntry, ("template", "background_option"), ()),
        (StartingEquipmentBackgroundLine, ("background_entry", "item"), ()),
        (StartingEquipmentLevelCoins, ("template",), ()),
        (MagicItemStartingOption, ("template", "item"), ()),
        (StartingEquipmentRequest, ("club", "character", "item"), ("message",)),
    ],
)
def test_starting_equipment_admin_fk_widgets(model_class, expected_autocomplete, expected_raw_id):
    """Each admin has the correct autocomplete_fields and raw_id_fields."""
    model_admin = _get_model_admin(model_class)
    assert model_admin is not None, f"{model_class.__name__} not registered"
    assert tuple(model_admin.autocomplete_fields) == expected_autocomplete
    assert tuple(model_admin.raw_id_fields) == expected_raw_id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class,fixture_name,expected_autocomplete,expected_raw_id",
    [
        (StartingEquipmentTemplate, "template", ("club",), ()),
        (StartingEquipmentClassEntry, "class_entry", ("template", "class_option"), ()),
        (StartingEquipmentClassLine, "class_line", ("class_entry", "item"), ()),
        (StartingEquipmentBackgroundEntry, "bg_entry", ("template", "background_option"), ()),
        (StartingEquipmentBackgroundLine, "bg_line", ("background_entry", "item"), ()),
        (StartingEquipmentLevelCoins, "level_coins", ("template",), ()),
        (MagicItemStartingOption, "magic_option", ("template", "item"), ()),
        (StartingEquipmentRequest, "pending_request", ("club", "character", "item"), ("message",)),
    ],
)
def test_starting_equipment_admin_change_form_widgets(
    site_admin, login, request, model_class, fixture_name, expected_autocomplete, expected_raw_id
):
    """Change form renders autocomplete widgets (admin-autocomplete) or raw_id widget."""
    obj = request.getfixturevalue(fixture_name)
    client = login(site_admin)
    _get_model_admin(model_class)
    change_url = reverse(
        f"admin:starting_equipment_{model_class.__name__.lower()}_change", args=[obj.pk]
    )
    response = client.get(change_url)
    assert response.status_code == 200
    content = response.content.decode()

    for field in expected_autocomplete:
        assert f'data-field-name="{field}"' in content, f"Missing autocomplete field {field}"
        assert "admin-autocomplete" in content, f"Missing admin-autocomplete class for {field}"

    for field in expected_raw_id:
        # raw_id widget uses vForeignKeyRawIdAdminField class on the input
        assert f'id="id_{field}"' in content, f"Missing raw_id field {field}"
        assert "vForeignKeyRawIdAdminField" in content, f"Missing raw_id widget for {field}"


@pytest.mark.django_db
def test_starting_equipment_admin_post_valid_change(site_admin, login, class_entry, class_line):
    """POST a valid change to a StartingEquipmentClassEntry and assert it saves."""
    client = login(site_admin)
    url = reverse(
        "admin:starting_equipment_startingequipmentclassentry_change", args=[class_entry.pk]
    )

    # Get the form first to get CSRF token
    response = client.get(url)
    assert response.status_code == 200

    # POST a valid change (update coins_cp)
    # Include inline formset management forms for the lines inline
    data = {
        "template": class_entry.template.pk,
        "class_option": class_entry.class_option.pk,
        "min_level": class_entry.min_level,
        "max_level": class_entry.max_level,
        "coins_cp": 2000,  # Changed from 1000
        # Inline formset management for StartingEquipmentClassLineInline
        "lines-TOTAL_FORMS": "1",
        "lines-INITIAL_FORMS": "1",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-id": str(class_line.pk),
        "lines-0-class_entry": str(class_entry.pk),
        "lines-0-item": str(class_line.item.pk),
        "lines-0-quantity": str(class_line.quantity),
        "lines-0-is_choice": str(class_line.is_choice).lower(),
        "lines-0-choice_group": class_line.choice_group,
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200

    class_entry.refresh_from_db()
    assert class_entry.coins_cp == 2000


@pytest.mark.django_db
def test_starting_equipment_request_admin_approve_action(site_admin, login, pending_request):
    """Approve action sets status to APPROVED and fills decided_by/decided_at."""
    client = login(site_admin)
    url = reverse("admin:starting_equipment_startingequipmentrequest_changelist")

    # POST the approve action
    data = {
        "action": "approve_requests",
        "_selected_action": [str(pending_request.pk)],
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200

    pending_request.refresh_from_db()
    assert pending_request.status == StartingEquipmentRequest.Status.APPROVED
    assert pending_request.decided_by == site_admin
    assert pending_request.decided_at is not None


@pytest.mark.django_db
def test_starting_equipment_request_admin_decline_action(site_admin, login, pending_request):
    """Decline action sets status to DECLINED and fills decided_by/decided_at."""
    client = login(site_admin)
    url = reverse("admin:starting_equipment_startingequipmentrequest_changelist")

    # POST the decline action
    data = {
        "action": "decline_requests",
        "_selected_action": [str(pending_request.pk)],
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200

    pending_request.refresh_from_db()
    assert pending_request.status == StartingEquipmentRequest.Status.DECLINED
    assert pending_request.decided_by == site_admin
    assert pending_request.decided_at is not None


@pytest.mark.django_db
def test_starting_equipment_admin_run_checks_no_errors():
    """django.core.checks.run_checks() shows no admin errors."""
    errors = checks.run_checks()
    admin_errors = [e for e in errors if e.id.startswith("admin.")]
    assert not admin_errors, f"Admin errors: {admin_errors}"
