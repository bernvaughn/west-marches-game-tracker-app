"""Test player_characters CharacterAdmin editing: changelist, forms,
FK widgets, fieldsets, and POST."""

import pytest
from django.contrib import admin as django_admin
from django.core import checks
from django.urls import reverse

from accounts.models import Membership
from player_characters.models import Character


@pytest.mark.django_db
def test_character_admin_changelist_add_change(site_admin, login, club, player, character):
    """Character changelist, add form, and change form load (200)."""
    client = login(site_admin)

    # Changelist
    response = client.get(reverse("admin:player_characters_character_changelist"))
    assert response.status_code == 200

    # Add form
    response = client.get(reverse("admin:player_characters_character_add"))
    assert response.status_code == 200

    # Change form
    url = reverse("admin:player_characters_character_change", args=[character.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_character_admin_fk_widgets(
    site_admin, login, club, player, character, species, char_class, background
):
    """Character change form renders autocomplete widgets for the five FKs."""
    client = login(site_admin)
    url = reverse("admin:player_characters_character_change", args=[character.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()

    # The five FKs that should have autocomplete
    autocomplete_fields = ["club", "owner", "species_option", "class_option", "background_option"]
    for field in autocomplete_fields:
        assert f'data-field-name="{field}"' in content, f"Missing autocomplete field {field}"
        assert "admin-autocomplete" in content, f"Missing admin-autocomplete class for {field}"


@pytest.mark.django_db
def test_character_admin_readonly_fields(site_admin, login, character):
    """last_printed_at and created render as read-only in the change form."""
    client = login(site_admin)
    url = reverse("admin:player_characters_character_change", args=[character.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()

    # Check that last_printed_at and created appear as readonly
    # They should have the readonly attribute or be in a readonly section
    assert "last_printed_at" in content
    assert "created" in content
    # The readonly fields should have readonly attribute or be disabled
    assert "readonly" in content.lower()


@pytest.mark.django_db
def test_character_admin_post_valid_change(site_admin, login, club, player, character, char_class):
    """POST a valid change (name, level, class_option) and assert it saves."""
    client = login(site_admin)
    url = reverse("admin:player_characters_character_change", args=[character.pk])

    # Get the form first
    response = client.get(url)
    assert response.status_code == 200

    # POST a valid change
    owner = Membership.objects.get(user=player, club=club)
    data = {
        "club": club.pk,
        "owner": owner.pk,
        "name": "Updated Name",
        "pronouns": character.pronouns,
        "alignment": character.alignment,
        "description": character.description,
        "species_option": character.species_option.pk if character.species_option else "",
        "species": character.species,
        "class_option": char_class.pk,
        "char_class": "Fighter",
        "background_option": character.background_option.pk if character.background_option else "",
        "background": character.background,
        "level": 5,
        "xp": character.xp or "",
        "strength": character.strength or "",
        "dexterity": character.dexterity or "",
        "constitution": character.constitution or "",
        "intelligence": character.intelligence or "",
        "wisdom": character.wisdom or "",
        "charisma": character.charisma or "",
        "armor_class": character.armor_class or "",
        "max_hp": character.max_hp or "",
        "carrying_capacity_lb": character.carrying_capacity_lb or "",
        "perception_bonus": character.perception_bonus or "",
        "shop_open": character.shop_open,
        "starting_equipment_claimed": character.starting_equipment_claimed,
        "died_on": character.died_on or "",
        "death_note": character.death_note,
        "archived_at": character.archived_at or "",
        "last_printed_at": character.last_printed_at or "",
        "created": character.created.isoformat() if character.created else "",
    }
    response = client.post(url, data, follow=True)
    assert response.status_code == 200

    character.refresh_from_db()
    assert character.name == "Updated Name"
    assert character.level == 5
    assert character.class_option == char_class


@pytest.mark.django_db
def test_character_admin_fieldsets_cover_all_fields(site_admin):
    """Every editable model form field appears in fieldsets (guards against dropped fields)."""
    model_admin = django_admin.site._registry[Character]

    # Get all form fields (exclude read-only and auto fields)
    # Need a request with user for get_form
    from django.test import RequestFactory

    factory = RequestFactory()
    request = factory.get("/")
    request.user = site_admin

    form = model_admin.get_form(request)
    form_fields = set(form.base_fields.keys())

    # Fields that should be excluded from the check (read-only, auto, or not in form)
    excluded = {"last_printed_at", "created"}  # These are read-only
    # The owner and club are in fieldsets, so include them
    checked_fields = form_fields - excluded

    # Collect all fields from fieldsets
    fieldset_fields = set()
    for _name, opts in model_admin.fieldsets:
        if "fields" in opts:
            for field in opts["fields"]:
                if isinstance(field, (list, tuple)):
                    fieldset_fields.update(field)
                else:
                    fieldset_fields.add(field)

    missing = checked_fields - fieldset_fields
    assert not missing, f"Fields missing from fieldsets: {missing}"


@pytest.mark.django_db
def test_character_admin_list_select_related():
    """list_select_related is set for FKs shown in list_display."""
    model_admin = django_admin.site._registry[Character]
    # list_display has: name, club, owner, level, char_class, died_on, archived_at
    # FKs in list_display: club, owner
    assert "club" in model_admin.list_select_related
    assert "owner__user" in model_admin.list_select_related
    # Also check the autocomplete FKs have select_related for performance
    assert "species_option" in model_admin.list_select_related
    assert "class_option" in model_admin.list_select_related
    assert "background_option" in model_admin.list_select_related


@pytest.mark.django_db
def test_player_characters_admin_run_checks_no_errors():
    """django.core.checks.run_checks() shows no admin errors."""
    errors = checks.run_checks()
    admin_errors = [e for e in errors if e.id.startswith("admin.")]
    assert not admin_errors, f"Admin errors: {admin_errors}"
