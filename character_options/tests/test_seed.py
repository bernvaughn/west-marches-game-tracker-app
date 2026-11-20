"""Tests for seed_default_options service."""

import pytest

from character_options.defaults import (
    DEFAULT_BACKGROUNDS,
    DEFAULT_CLASSES,
    DEFAULT_SPECIES,
)
from character_options.models import Background, CharacterClass, Species
from character_options.services import seed_default_options


@pytest.mark.django_db
def test_seed_creates_all_defaults(club):
    """Seed creates all default records with correct counts."""
    result = seed_default_options(club)

    assert result == {
        "species": len(DEFAULT_SPECIES),
        "classes": len(DEFAULT_CLASSES),
        "backgrounds": len(DEFAULT_BACKGROUNDS),
    }
    assert Species.objects.for_club(club).count() == len(DEFAULT_SPECIES)
    assert CharacterClass.objects.for_club(club).count() == len(DEFAULT_CLASSES)
    assert Background.objects.for_club(club).count() == len(DEFAULT_BACKGROUNDS)


@pytest.mark.django_db
def test_seed_is_idempotent(club):
    """Second call creates nothing and counts unchanged."""
    seed_default_options(club)
    first_counts = {
        "species": Species.objects.for_club(club).count(),
        "classes": CharacterClass.objects.for_club(club).count(),
        "backgrounds": Background.objects.for_club(club).count(),
    }

    result = seed_default_options(club)

    assert result == {"species": 0, "classes": 0, "backgrounds": 0}
    assert Species.objects.for_club(club).count() == first_counts["species"]
    assert CharacterClass.objects.for_club(club).count() == first_counts["classes"]
    assert Background.objects.for_club(club).count() == first_counts["backgrounds"]


@pytest.mark.django_db
def test_seed_does_not_resurrect_archived(club):
    """Archived records stay archived; no duplicate appears."""
    seed_default_options(club)
    wizard = CharacterClass.objects.for_club(club).get(name="Wizard")
    wizard.is_active = False
    wizard.save()

    seed_default_options(club)

    wizard.refresh_from_db()
    assert wizard.is_active is False
    assert CharacterClass.objects.for_club(club).filter(name="Wizard").count() == 1


@pytest.mark.django_db
def test_seed_recreates_renamed(club):
    """Renamed record causes original name to be recreated."""
    seed_default_options(club)
    bard = CharacterClass.objects.for_club(club).get(name="Bard")
    bard.name = "Skald"
    bard.save()

    seed_default_options(club)

    assert CharacterClass.objects.for_club(club).filter(name="Bard").exists()
    assert CharacterClass.objects.for_club(club).filter(name="Skald").exists()
    assert CharacterClass.objects.for_club(club).count() == len(DEFAULT_CLASSES) + 1


@pytest.mark.django_db
def test_seed_per_club_isolation(club, other_club):
    """Seeding club A leaves club B empty."""
    seed_default_options(club)

    assert Species.objects.for_club(club).count() == len(DEFAULT_SPECIES)
    assert Species.objects.for_club(other_club).count() == 0
    assert CharacterClass.objects.for_club(other_club).count() == 0
    assert Background.objects.for_club(other_club).count() == 0


@pytest.mark.django_db
def test_seed_new_club_via_view(club, site_admin, login):
    """New club via club_new view gets seeded."""
    client = login(site_admin)
    from django.urls import reverse

    # Create a new club via the view
    response = client.post(
        reverse("site_club_new"),
        {
            "name": "New Club",
            "slug": "new-club",
            "admin_email": "newadmin@example.com",
            "admin_display_name": "New Admin",
        },
    )
    assert response.status_code == 200

    from accounts.models import Club

    new_club = Club.objects.get(slug="new-club")
    assert Species.objects.for_club(new_club).count() == len(DEFAULT_SPECIES)
    assert CharacterClass.objects.for_club(new_club).count() == len(DEFAULT_CLASSES)
    assert Background.objects.for_club(new_club).count() == len(DEFAULT_BACKGROUNDS)


@pytest.mark.django_db
def test_demo_seed_is_idempotent(db):
    """accounts.demo.seed() seeds demo club and is idempotent."""
    from accounts.demo import seed as demo_seed

    club = demo_seed()
    first_species = Species.objects.for_club(club).count()
    first_classes = CharacterClass.objects.for_club(club).count()
    first_backgrounds = Background.objects.for_club(club).count()

    club = demo_seed()

    assert Species.objects.for_club(club).count() == first_species
    assert CharacterClass.objects.for_club(club).count() == first_classes
    assert Background.objects.for_club(club).count() == first_backgrounds
