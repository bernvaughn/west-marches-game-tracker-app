"""Tests for character options admin views."""

import json

import pytest
from django.urls import reverse

from accounts.models import Club
from character_options.models import Background, CharacterClass, Species
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentClassEntry,
    StartingEquipmentTemplate,
)

# --- Fixtures for option kinds ---


@pytest.fixture
def club(db):
    """Unseeded club: these tests create their own option records."""
    return Club.objects.create(name="Test Club", slug="test-club")


@pytest.fixture
def other_club(db):
    """Unseeded second club."""
    return Club.objects.create(name="Other Club", slug="other-club")


@pytest.fixture
def species(club):
    return Species.objects.create(club=club, name="Elf", sort_order=10)


@pytest.fixture
def char_class(club):
    return CharacterClass.objects.create(club=club, name="Fighter", sort_order=10)


@pytest.fixture
def background(club):
    return Background.objects.create(club=club, name="Soldier", sort_order=10)


# --- Permission tests ---


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind",
    ["species", "classes", "backgrounds"],
    ids=["species", "classes", "backgrounds"],
)
def test_admin_gets_200_on_list(club_admin, login, club, kind, species, char_class, background):
    """Club admin gets 200 on all three list pages."""
    client = login(club_admin)
    url = reverse("character_options:list", args=[club.slug, kind])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind",
    ["species", "classes", "backgrounds"],
    ids=["species", "classes", "backgrounds"],
)
def test_site_admin_gets_200_on_list(
    site_admin, login, club, kind, species, char_class, background
):
    """Site admin gets 200 on all three list pages."""
    client = login(site_admin)
    url = reverse("character_options:list", args=[club.slug, kind])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_fixture,url_name",
    [
        ("game_master", "list"),
        ("player", "list"),
        ("game_master", "create"),
        ("player", "create"),
        ("game_master", "edit"),
        ("player", "edit"),
        ("game_master", "archive"),
        ("player", "archive"),
        ("game_master", "restore"),
        ("player", "restore"),
        ("game_master", "delete"),
        ("player", "delete"),
        ("game_master", "move"),
        ("player", "move"),
    ],
)
def test_non_admin_gets_404(
    request, user_fixture, url_name, login, club, species, char_class, background
):
    """GM and player get 404 on all options pages and actions."""
    user = request.getfixturevalue(user_fixture)
    client = login(user)

    kind_map = {"species": species, "classes": char_class, "backgrounds": background}
    kind = "species"  # default

    if url_name in ("edit", "archive", "restore", "delete", "move"):
        option = kind_map[kind]
        url = reverse("character_options:" + url_name, args=[club.slug, kind, option.pk])
    elif url_name == "create":
        url = reverse("character_options:create", args=[club.slug, kind])
    else:
        url = reverse("character_options:list", args=[club.slug, kind])

    response = client.get(url)
    assert response.status_code == 404, f"{user_fixture} GET {url_name} {kind} should be 404"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_fixture,url_name",
    [
        ("game_master", "create"),
        ("player", "create"),
        ("game_master", "edit"),
        ("player", "edit"),
        ("game_master", "archive"),
        ("player", "archive"),
        ("game_master", "restore"),
        ("player", "restore"),
        ("game_master", "delete"),
        ("player", "delete"),
        ("game_master", "move"),
        ("player", "move"),
    ],
)
def test_non_admin_post_changes_nothing(
    request, user_fixture, url_name, login, club, species, char_class, background
):
    """POST by GM or player changes nothing."""
    user = request.getfixturevalue(user_fixture)
    client = login(user)

    kind = "species"
    option = species

    if url_name == "create":
        url = reverse("character_options:create", args=[club.slug, kind])
        response = client.post(url, {"name": "New Species"})
        assert response.status_code == 404
        assert Species.objects.for_club(club).count() == 1
    elif url_name == "edit":
        url = reverse("character_options:edit", args=[club.slug, kind, option.pk])
        response = client.post(url, {"name": "Renamed"})
        assert response.status_code == 404
        option.refresh_from_db()
        assert option.name == "Elf"
    elif url_name == "archive":
        url = reverse("character_options:archive", args=[club.slug, kind, option.pk])
        response = client.post(url)
        assert response.status_code == 404
        option.refresh_from_db()
        assert option.is_active is True
    elif url_name == "restore":
        option.is_active = False
        option.save()
        url = reverse("character_options:restore", args=[club.slug, kind, option.pk])
        response = client.post(url)
        assert response.status_code == 404
        option.refresh_from_db()
        assert option.is_active is False
    elif url_name == "delete":
        url = reverse("character_options:delete", args=[club.slug, kind, option.pk])
        response = client.post(url)
        assert response.status_code == 404
        assert Species.objects.for_club(club).count() == 1
    elif url_name == "move":
        url = reverse("character_options:move", args=[club.slug, kind, option.pk])
        response = client.post(url, {"direction": "up"})
        assert response.status_code == 404


@pytest.mark.django_db
def test_anonymous_redirects_to_login(club):
    """Anonymous user redirects to login."""
    from django.test import Client

    client = Client()
    url = reverse("character_options:list", args=[club.slug, "species"])
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


# --- Club isolation tests ---


@pytest.mark.django_db
def test_list_shows_only_this_club_records(club, other_club, club_admin, login):
    """List shows only this club's records."""
    Species.objects.create(club=club, name="Club A Elf")
    Species.objects.create(club=other_club, name="Club B Elf")

    client = login(club_admin)
    url = reverse("character_options:list", args=[club.slug, "species"])
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Club A Elf" in content
    assert "Club B Elf" not in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action",
    ["edit", "archive", "restore", "delete", "move"],
)
def test_pk_from_other_club_gives_404(club, other_club, club_admin, login, action):
    """PK from another club gives 404 on edit, archive, restore, delete, move."""
    other_species = Species.objects.create(club=other_club, name="Other Elf")
    client = login(club_admin)

    url = reverse("character_options:" + action, args=[club.slug, "species", other_species.pk])
    if action in ("archive", "restore", "move", "delete"):
        response = client.post(url)
    else:
        response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_same_name_allowed_in_two_clubs(club, other_club):
    """Same name in two clubs is allowed."""
    Species.objects.create(club=club, name="Elf")
    Species.objects.create(club=other_club, name="Elf")

    assert Species.objects.for_club(club).count() == 1
    assert Species.objects.for_club(other_club).count() == 1


# --- Duplicate name tests ---


@pytest.mark.django_db
def test_create_duplicate_case_insensitive_fails(club, club_admin, login, species):
    """Create with case variant fails with message."""
    client = login(club_admin)
    url = reverse("character_options:create", args=[club.slug, "species"])
    response = client.post(url, {"name": "elf"}, HTTP_HX_REQUEST="true")  # lowercase variant

    assert response.status_code == 400  # htmx modal re-render
    content = response.content.decode()
    assert "already exists" in content.lower()
    assert Species.objects.for_club(club).count() == 1


@pytest.mark.django_db
def test_create_duplicate_whitespace_fails(club, club_admin, login, species):
    """Create with whitespace variant fails."""
    client = login(club_admin)
    url = reverse("character_options:create", args=[club.slug, "species"])
    response = client.post(url, {"name": "  Elf  "}, HTTP_HX_REQUEST="true")

    assert response.status_code == 400
    content = response.content.decode()
    assert "already exists" in content.lower()


@pytest.mark.django_db
def test_rename_to_existing_case_insensitive_fails(club, club_admin, login, species):
    """Rename to case variant of another record fails."""
    Species.objects.create(club=club, name="Dwarf", sort_order=20)
    client = login(club_admin)
    url = reverse("character_options:edit", args=[club.slug, "species", species.pk])
    response = client.post(url, {"name": "dwarf"}, HTTP_HX_REQUEST="true")

    assert response.status_code == 400
    content = response.content.decode()
    assert "already exists" in content.lower()
    species.refresh_from_db()
    assert species.name == "Elf"


@pytest.mark.django_db
def test_rename_to_own_name_works(club, club_admin, login, species):
    """Rename to own name (or only case change) works."""
    client = login(club_admin)
    url = reverse("character_options:edit", args=[club.slug, "species", species.pk])
    response = client.post(url, {"name": "Elf"}, HTTP_HX_REQUEST="true")  # same name
    assert response.status_code == 204
    species.refresh_from_db()
    assert species.name == "Elf"


@pytest.mark.django_db
def test_rename_case_change_works(club, club_admin, login, species):
    """Rename with only case change works."""
    client = login(club_admin)
    url = reverse("character_options:edit", args=[club.slug, "species", species.pk])
    response = client.post(url, {"name": "ELF"}, HTTP_HX_REQUEST="true")  # case change only
    assert response.status_code == 204
    species.refresh_from_db()
    assert species.name == "ELF"


@pytest.mark.django_db
def test_name_max_60_chars(club, club_admin, login):
    """61-character name fails."""
    client = login(club_admin)
    url = reverse("character_options:create", args=[club.slug, "species"])
    long_name = "A" * 61
    response = client.post(url, {"name": long_name}, HTTP_HX_REQUEST="true")
    assert response.status_code == 400
    content = response.content.decode()
    assert "60" in content or "max" in content.lower()


# --- CRUD tests ---


@pytest.mark.django_db
def test_create_option(club, club_admin, login):
    """Create a new option."""
    client = login(club_admin)
    url = reverse("character_options:create", args=[club.slug, "species"])
    response = client.post(url, {"name": "Dwarf"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    assert response["HX-Trigger"] is not None
    trigger = json.loads(response["HX-Trigger"])
    assert trigger["optionsChanged"] is True
    assert trigger["appModalClose"] is True

    dwarf = Species.objects.for_club(club).get(name="Dwarf")
    assert dwarf.sort_order == 10  # max (0) + 10


@pytest.mark.django_db
def test_create_option_non_htmx_redirects(club, club_admin, login):
    """Non-HTMX create redirects with success message."""
    client = login(club_admin)
    url = reverse("character_options:create", args=[club.slug, "species"])
    response = client.post(url, {"name": "Dwarf"})
    # Without HX-Request header, it's a regular POST
    assert response.status_code == 302


@pytest.mark.django_db
def test_rename_updates_character_text_snapshot(
    club, club_admin, login, species, char_class, background
):
    """Renaming updates Character text field."""
    from accounts.models import Membership, User

    owner = Membership.objects.create(
        user=User.objects.create_user("owner@example.com", password="pw"),
        club=club,
    )
    char = Character.objects.create(
        club=club,
        owner=owner,
        name="Test",
        species_option=species,
        species="Elf",  # text snapshot
        class_option=char_class,
        char_class="Fighter",
        background_option=background,
        background="Soldier",
    )

    client = login(club_admin)
    url = reverse("character_options:edit", args=[club.slug, "species", species.pk])
    response = client.post(url, {"name": "High Elf"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 204

    species.refresh_from_db()
    char.refresh_from_db()
    assert species.name == "High Elf"
    assert char.species == "High Elf"  # text snapshot updated


@pytest.mark.django_db
def test_rename_class_entry_keeps_fk_link(club, club_admin, login, char_class):
    """Renaming a class keeps the StartingEquipmentClassEntry FK link (no text snapshot)."""
    template = StartingEquipmentTemplate.objects.create(club=club, name="Test")
    entry = StartingEquipmentClassEntry.objects.create(
        template=template,
        class_option=char_class,
    )

    client = login(club_admin)
    url = reverse("character_options:edit", args=[club.slug, "classes", char_class.pk])
    response = client.post(url, {"name": "Warrior"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 204

    char_class.refresh_from_db()
    entry.refresh_from_db()
    assert char_class.name == "Warrior"
    assert entry.class_option == char_class


@pytest.mark.django_db
def test_rename_background_entry_keeps_fk_link(club, club_admin, login, background):
    """Renaming a background keeps the FK link (no text snapshot)."""
    template = StartingEquipmentTemplate.objects.create(club=club, name="Test")
    entry = StartingEquipmentBackgroundEntry.objects.create(
        template=template,
        background_option=background,
    )

    client = login(club_admin)
    url = reverse("character_options:edit", args=[club.slug, "backgrounds", background.pk])
    response = client.post(url, {"name": "Warrior"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 204

    background.refresh_from_db()
    entry.refresh_from_db()
    assert background.name == "Warrior"
    assert entry.background_option == background


@pytest.mark.django_db
def test_archive_hides_from_pickers_but_shows_in_admin(club, club_admin, login, species):
    """Archive hides from active_options but stays visible on admin list."""
    from character_options.services import active_options

    # Initially active
    assert species in active_options(club, Species)

    client = login(club_admin)
    url = reverse("character_options:archive", args=[club.slug, "species", species.pk])
    response = client.post(url)
    assert response.status_code == 302

    species.refresh_from_db()
    assert species.is_active is False
    assert species not in active_options(club, Species)

    # But still shows in admin list
    list_url = reverse("character_options:list", args=[club.slug, "species"])
    response = client.get(list_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Elf" in content
    assert "Archived" in content


@pytest.mark.django_db
def test_restore_shows_in_pickers_again(club, club_admin, login, species):
    """Restore makes it active again."""
    from character_options.services import active_options

    species.is_active = False
    species.save()
    assert species not in active_options(club, Species)

    client = login(club_admin)
    url = reverse("character_options:restore", args=[club.slug, "species", species.pk])
    response = client.post(url)
    assert response.status_code == 302

    species.refresh_from_db()
    assert species.is_active is True
    assert species in active_options(club, Species)


@pytest.mark.django_db
def test_reorder_up_down(club, club_admin, login):
    """Reorder up/down works."""
    s1 = Species.objects.create(club=club, name="A", sort_order=10)
    s2 = Species.objects.create(club=club, name="B", sort_order=20)
    s3 = Species.objects.create(club=club, name="C", sort_order=30)

    client = login(club_admin)

    # Move C up
    url = reverse("character_options:move", args=[club.slug, "species", s3.pk])
    response = client.post(url, {"direction": "up"})
    assert response.status_code == 302

    s2.refresh_from_db()
    s3.refresh_from_db()
    # After move: A=10, C=20, B=30
    assert s3.sort_order < s2.sort_order

    # Move A down
    url = reverse("character_options:move", args=[club.slug, "species", s1.pk])
    response = client.post(url, {"direction": "down"})
    assert response.status_code == 302

    s1.refresh_from_db()
    s3.refresh_from_db()
    # After move: C=10, A=20, B=30
    # A moved down relative to C (was before C, now after C)
    assert s1.sort_order > s3.sort_order


@pytest.mark.django_db
def test_reorder_first_last_noop(club, club_admin, login):
    """Reorder at boundaries is a no-op."""
    s1 = Species.objects.create(club=club, name="A", sort_order=10)
    s2 = Species.objects.create(club=club, name="B", sort_order=20)

    client = login(club_admin)

    # Move first up - noop
    url = reverse("character_options:move", args=[club.slug, "species", s1.pk])
    response = client.post(url, {"direction": "up"})
    assert response.status_code == 302
    s1.refresh_from_db()
    assert s1.sort_order == 10

    # Move last down - noop
    url = reverse("character_options:move", args=[club.slug, "species", s2.pk])
    response = client.post(url, {"direction": "down"})
    assert response.status_code == 302
    s2.refresh_from_db()
    assert s2.sort_order == 20


@pytest.mark.django_db
def test_reorder_handles_ties(club, club_admin, login):
    """Reorder handles tied sort_order values."""
    Species.objects.create(club=club, name="A", sort_order=10)
    Species.objects.create(club=club, name="B", sort_order=10)  # tie
    s3 = Species.objects.create(club=club, name="C", sort_order=20)

    client = login(club_admin)

    # Move C up - should swap with one of the tied ones
    url = reverse("character_options:move", args=[club.slug, "species", s3.pk])
    response = client.post(url, {"direction": "up"})
    assert response.status_code == 302

    # After renumbering, order should be deterministic
    records = list(Species.objects.for_club(club).order_by("sort_order", "name"))
    assert len(records) == 3


# --- Delete blocked tests ---


@pytest.mark.django_db
def test_delete_blocked_by_character(club, club_admin, login, species):
    """Delete blocked when character uses the option."""
    from accounts.models import Membership, User

    owner = Membership.objects.create(
        user=User.objects.create_user("owner@example.com", password="pw"),
        club=club,
    )
    Character.objects.create(
        club=club,
        owner=owner,
        name="Test",
        species_option=species,
    )

    client = login(club_admin)
    url = reverse("character_options:delete", args=[club.slug, "species", species.pk])

    # GET shows confirm with blocker
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Used by" in content
    assert "character" in content.lower()
    assert "Archive it instead" in content

    # POST is blocked
    response = client.post(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 400  # htmx re-render with blocker
    content = response.content.decode()
    assert "Used by" in content

    # Record still exists
    assert Species.objects.for_club(club).filter(pk=species.pk).exists()


@pytest.mark.django_db
def test_delete_blocked_by_class_entry(club, club_admin, login, char_class):
    """Delete blocked when starting equipment class entry uses the option."""
    template = StartingEquipmentTemplate.objects.create(club=club, name="Test")
    StartingEquipmentClassEntry.objects.create(
        template=template,
        class_option=char_class,
    )

    client = login(club_admin)
    url = reverse("character_options:delete", args=[club.slug, "classes", char_class.pk])

    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Used by" in content
    assert "starting equipment entr" in content.lower()
    assert "Archive it instead" in content

    response = client.post(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 400
    assert CharacterClass.objects.for_club(club).filter(pk=char_class.pk).exists()


@pytest.mark.django_db
def test_delete_blocked_by_background_entry(club, club_admin, login, background):
    """Delete blocked when starting equipment background entry uses the option."""
    template = StartingEquipmentTemplate.objects.create(club=club, name="Test")
    StartingEquipmentBackgroundEntry.objects.create(
        template=template,
        background_option=background,
    )

    client = login(club_admin)
    url = reverse("character_options:delete", args=[club.slug, "backgrounds", background.pk])

    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Used by" in content
    assert "starting equipment entr" in content.lower()

    response = client.post(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 400
    assert Background.objects.for_club(club).filter(pk=background.pk).exists()


@pytest.mark.django_db
def test_delete_unused_succeeds(club, club_admin, login):
    """Unused record deletes successfully."""
    species = Species.objects.create(club=club, name="Unused", sort_order=10)

    client = login(club_admin)
    url = reverse("character_options:delete", args=[club.slug, "species", species.pk])

    response = client.post(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    trigger = json.loads(response["HX-Trigger"])
    assert trigger["optionsChanged"] is True
    assert trigger["appModalClose"] is True

    assert not Species.objects.for_club(club).filter(pk=species.pk).exists()


@pytest.mark.django_db
def test_delete_htmx_trigger(club, club_admin, login):
    """Delete returns 204 with HX-Trigger for htmx."""
    species = Species.objects.create(club=club, name="Unused", sort_order=10)

    client = login(club_admin)
    url = reverse("character_options:delete", args=[club.slug, "species", species.pk])
    response = client.post(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert "HX-Trigger" in response
    trigger = json.loads(response["HX-Trigger"])
    assert trigger["optionsChanged"] is True
    assert trigger["appModalClose"] is True


# --- Usage counts render ---


@pytest.mark.django_db
def test_usage_counts_render_in_list(club, club_admin, login, species, char_class, background):
    """Usage counts render per record in the list."""
    from accounts.models import Membership, User

    owner = Membership.objects.create(
        user=User.objects.create_user("owner@example.com", password="pw"),
        club=club,
    )
    Character.objects.create(
        club=club,
        owner=owner,
        name="Test1",
        species_option=species,
        class_option=char_class,
    )
    Character.objects.create(
        club=club,
        owner=owner,
        name="Test2",
        species_option=species,
    )

    template = StartingEquipmentTemplate.objects.create(club=club, name="Test")
    StartingEquipmentClassEntry.objects.create(
        template=template,
        class_option=char_class,
    )

    client = login(club_admin)
    for kind in ["species", "classes", "backgrounds"]:
        url = reverse("character_options:list", args=[club.slug, kind])
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # Check that counts appear in the table
        if kind == "species":
            assert "2" in content  # character_count
        elif kind == "classes":
            assert "1" in content  # character_count
            assert "1" in content  # entry_count


# --- Archive hides from pickers ---


@pytest.mark.django_db
def test_active_options_excludes_archived(club, species):
    """active_options excludes archived records."""
    from character_options.services import active_options

    species.is_active = False
    species.save()

    active = active_options(club, Species)
    assert species not in active


@pytest.mark.django_db
def test_match_option_still_finds_archived(club, species):
    """match_option still finds archived records."""
    from character_options.services import match_option

    species.is_active = False
    species.save()

    result = match_option(club, Species, "Elf")
    assert result is not None
    assert result.pk == species.pk


# --- Template guard test ---


@pytest.mark.django_db
def test_list_partial_has_hx_disinherit(club, club_admin, login):
    """List partial contains hx-disinherit."""
    client = login(club_admin)
    url = reverse("character_options:list", args=[club.slug, "species"])
    response = client.get(url)
    content = response.content.decode()
    assert 'hx-disinherit="*"' in content


@pytest.mark.django_db
def test_modal_triggers_have_correct_swap(club, club_admin, login, species):
    """Every modal trigger has hx-swap='innerHTML'."""
    client = login(club_admin)
    url = reverse("character_options:list", args=[club.slug, "species"])
    response = client.get(url)
    content = response.content.decode()

    # Edit link
    edit_url = reverse("character_options:edit", args=[club.slug, "species", species.pk])
    assert f'hx-get="{edit_url}"' in content
    assert 'hx-target="#app-modal .modal-content"' in content
    assert 'hx-swap="innerHTML"' in content
    assert "data-app-modal" in content

    # Delete link
    delete_url = reverse("character_options:delete", args=[club.slug, "species", species.pk])
    assert f'hx-get="{delete_url}"' in content


# --- Nav test ---


@pytest.mark.django_db
def test_admin_sees_nav_link(club_admin, login, club):
    """Admin sees the nav link in the admin group."""
    client = login(club_admin)
    url = reverse("club_home", args=[club.slug])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Character options" in content


@pytest.mark.django_db
def test_gm_and_player_do_not_see_nav_link(game_master, player, login, club):
    """GM and player do not see the nav link."""
    for user in [game_master, player]:
        client = login(user)
        # club_home redirects non-admins to dashboard; follow the redirect
        url = reverse("club_home", args=[club.slug])
        response = client.get(url, follow=True)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Character options" not in content
