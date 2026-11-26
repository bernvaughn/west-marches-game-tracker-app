"""Test character_options admin changelists and change forms."""

import pytest
from django.urls import reverse

from character_options.models import Background, CharacterClass, Species


@pytest.mark.django_db
def test_species_admin_changelist_and_change(site_admin, login, club):
    """Species changelist and change form load."""
    species = Species.objects.create(club=club, name="Elf", is_active=True, sort_order=1)
    client = login(site_admin)

    # Changelist
    url = reverse("admin:character_options_species_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert b"Elf" in response.content

    # Change form
    url = reverse("admin:character_options_species_change", args=[species.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_characterclass_admin_changelist_and_change(site_admin, login, club):
    """CharacterClass changelist and change form load."""
    char_class = CharacterClass.objects.create(
        club=club, name="Fighter", is_active=True, sort_order=1
    )
    client = login(site_admin)

    # Changelist
    url = reverse("admin:character_options_characterclass_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert b"Fighter" in response.content

    # Change form
    url = reverse("admin:character_options_characterclass_change", args=[char_class.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_background_admin_changelist_and_change(site_admin, login, club):
    """Background changelist and change form load."""
    background = Background.objects.create(club=club, name="Soldier", is_active=True, sort_order=1)
    client = login(site_admin)

    # Changelist
    url = reverse("admin:character_options_background_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert b"Soldier" in response.content

    # Change form
    url = reverse("admin:character_options_background_change", args=[background.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_species_admin_list_display(site_admin, login, club):
    """Species admin shows correct fields in changelist."""
    Species.objects.create(club=club, name="Dwarf", is_active=False, sort_order=5)
    client = login(site_admin)

    url = reverse("admin:character_options_species_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Dwarf" in content
    assert "False" in content or "No" in content  # is_active
    assert "5" in content  # sort_order


@pytest.mark.django_db
def test_characterclass_admin_list_display(site_admin, login, club):
    """CharacterClass admin shows correct fields in changelist."""
    CharacterClass.objects.create(club=club, name="Wizard", is_active=True, sort_order=2)
    client = login(site_admin)

    url = reverse("admin:character_options_characterclass_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Wizard" in content
    assert "True" in content or "Yes" in content  # is_active
    assert "2" in content  # sort_order


@pytest.mark.django_db
def test_background_admin_list_display(site_admin, login, club):
    """Background admin shows correct fields in changelist."""
    Background.objects.create(club=club, name="Noble", is_active=True, sort_order=3)
    client = login(site_admin)

    url = reverse("admin:character_options_background_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Noble" in content
    assert "True" in content or "Yes" in content  # is_active
    assert "3" in content  # sort_order


def test_every_character_options_model_is_in_the_admin():
    """New character_options models must be registered, or named here with a reason."""
    from django.apps import apps
    from django.contrib import admin as django_admin

    left_out_on_purpose = set()
    registered = {m.__name__ for m in django_admin.site._registry}
    missing = (
        {m.__name__ for m in apps.get_app_config("character_options").get_models()}
        - registered
        - left_out_on_purpose
    )
    assert not missing, (
        f"Register these character_options models in character_options/admin.py: {sorted(missing)}"
    )
