"""Tests for the archived characters screen (U145)."""

import pytest
from django.urls import reverse
from django.utils import dateformat

pytestmark = pytest.mark.story("U145")


def archive_url(club):
    return reverse("characters:archived", args=[club.slug])


def _membership(user, club):
    from accounts.models import Membership

    return Membership.objects.get(user=user, club=club)


# --- Access ---


@pytest.mark.story("U145")
def test_anonymous_redirects(client, club):
    resp = client.get(archive_url(club))
    assert resp.status_code == 302


@pytest.mark.story("U145")
def test_non_member_404(client, club, login):
    """Non-members of the club get 404 (middleware behavior)."""
    from accounts.models import User

    user = User.objects.create_user("nomember@example.com", password="pw", display_name="No Member")
    resp = login(user).get(archive_url(club))
    assert resp.status_code == 404


# --- Visibility: players see only their own ---


@pytest.mark.story("U145")
def test_player_sees_only_own_archived(
    login, club, player, other_player, character, other_character
):
    """Player sees their own archived character, not another player's."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()
    other_character.archived_at = timezone.now()
    other_character.save()

    body = login(player).get(archive_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert f">{other_character.name}<" not in body


@pytest.mark.story("U145")
def test_living_character_not_listed(login, club, player, character):
    """A living (unarchived) character is not listed."""
    body = login(player).get(archive_url(club)).content.decode()
    assert f">{character.name}<" not in body


@pytest.mark.story("U145")
def test_owner_param_does_not_leak(login, club, player, other_player, character, other_character):
    """?owner=<other pk> does not leak another player's character to a player."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()
    other_character.archived_at = timezone.now()
    other_character.save()

    url = f"{archive_url(club)}?owner={other_player.pk}"
    body = login(player).get(url).content.decode()
    assert f">{character.name}<" in body
    assert f">{other_character.name}<" not in body


# --- GM / club admin / superuser see all ---


@pytest.mark.story("U145")
def test_gm_sees_all_with_owners(
    login, club, game_master, player, other_player, character, other_character
):
    """GM sees all archived characters with owner names."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()
    other_character.archived_at = timezone.now()
    other_character.save()

    body = login(game_master).get(archive_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert f">{other_character.name}<" in body
    assert character.owner.user.display_name in body
    assert other_character.owner.user.display_name in body


@pytest.mark.story("U145")
def test_club_admin_sees_all(login, club, club_admin, player, character, other_character):
    """Club admin sees all archived characters."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()
    other_character.archived_at = timezone.now()
    other_character.save()

    body = login(club_admin).get(archive_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert f">{other_character.name}<" in body


@pytest.mark.story("U145")
def test_superuser_sees_all(login, club, site_admin, player, character):
    """Site admin sees all archived characters."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()

    body = login(site_admin).get(archive_url(club)).content.decode()
    assert f">{character.name}<" in body


# --- Owner filter ---


@pytest.mark.story("U145")
def test_owner_filter_works(
    login, club, game_master, player, other_player, character, other_character
):
    """?owner=<membership pk> filters the archive list."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()
    other_character.archived_at = timezone.now()
    other_character.save()

    url = f"{archive_url(club)}?owner={other_player.pk}"
    body = login(game_master).get(url).content.decode()
    assert f">{other_character.name}<" in body
    assert f">{character.name}<" not in body


@pytest.mark.story("U145")
def test_junk_owner_shows_all(login, club, game_master, player, character):
    """Junk ?owner=abc shows all (ignored)."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()

    url = f"{archive_url(club)}?owner=abc"
    body = login(game_master).get(url).content.decode()
    assert f">{character.name}<" in body


@pytest.mark.story("U145")
def test_other_club_characters_not_shown(
    login, club, game_master, player, character, foreign_character
):
    """Characters from another club never appear."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()
    foreign_character.archived_at = timezone.now()
    foreign_character.save()

    body = login(game_master).get(archive_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert f">{foreign_character.name}<" not in body


# --- Row content ---


@pytest.mark.story("U145")
def test_row_shows_name_class_level_archived(login, club, player, character):
    """Row shows name, class, level, archive date."""
    from django.utils import timezone

    character.char_class = "Fighter"
    character.level = 3
    character.archived_at = timezone.now()
    character.save()

    body = login(player).get(archive_url(club)).content.decode()
    assert f">{character.name}<" in body
    assert "Fighter" in body
    assert "Level 3" in body
    assert dateformat.format(character.archived_at, "d M Y") in body


@pytest.mark.story("U145")
def test_dead_row_shows_died_date(login, club, player, character):
    """Dead row shows the died date; living row shows none."""
    from django.utils import timezone

    character.died_on = timezone.localdate()
    character.archived_at = timezone.now()
    character.save()

    body = login(player).get(archive_url(club)).content.decode()
    assert f"Died {dateformat.format(character.died_on, 'd M Y')}" in body


# --- Unarchive form ---


@pytest.mark.story("U145")
def test_row_has_unarchive_form(login, club, player, character):
    """Each row has a POST form whose action is the characters:unarchive URL."""
    from django.utils import timezone

    character.archived_at = timezone.now()
    character.save()

    body = login(player).get(archive_url(club)).content.decode()
    action = reverse("characters:unarchive", args=[club.slug, character.pk])
    assert f'action="{action}"' in body
    assert "csrfmiddlewaretoken" in body


# --- Service path: unarchive through life.unarchive ---


@pytest.mark.story("U145")
def test_unarchive_character_leaves_screen(login, club, player, character):
    """After unarchive the character leaves the screen and is in not_archived()."""
    from django.utils import timezone

    from player_characters import life
    from player_characters.models import Character

    character.archived_at = timezone.now()
    character.save()

    life.unarchive(character, by=_membership(player, club))

    assert not Character.objects.filter(pk=character.pk, archived_at__isnull=False).exists()
    assert character.pk in Character.objects.not_archived().values_list("pk", flat=True)


@pytest.mark.story("U145")
def test_dead_character_stays_dead_after_unarchive(login, club, player, character):
    """A dead character keeps died_on after unarchive."""
    from django.utils import timezone

    from player_characters import life

    character.died_on = timezone.localdate()
    character.archived_at = timezone.now()
    character.save()

    life.unarchive(character, by=_membership(player, club))

    character.refresh_from_db()
    assert character.died_on is not None
    assert character.archived_at is None


@pytest.mark.story("U145")
def test_shop_open_stays_false_after_unarchive(login, club, player, character):
    """shop_open stays False after archive then unarchive."""

    from player_characters import life

    character.shop_open = True
    character.save()

    life.archive(character, by=_membership(player, club))
    character.refresh_from_db()
    assert character.shop_open is False

    life.unarchive(character, by=_membership(player, club))
    character.refresh_from_db()
    assert character.shop_open is False


# --- Nav: side menu links to archive ---


@pytest.mark.story("U145")
def test_nav_links_archived(login, club, player, character):
    """The side menu for a player links characters:archived."""
    body = login(player).get(reverse("club_home", args=[club.slug]), follow=True).content.decode()
    archived_url = reverse("characters:archived", args=[club.slug])
    assert f'href="{archived_url}"' in body


# --- C8 end-to-end (service path, C8 view is a stub) ---


@pytest.mark.story("U145")
def test_unarchive_service_path(login, club, player, character):
    """life.unarchive returns the character to not_archived()."""
    from django.utils import timezone

    from player_characters import life
    from player_characters.models import Character

    character.archived_at = timezone.now()
    character.save()

    life.unarchive(character, by=_membership(player, club))
    character.refresh_from_db()
    assert character.archived_at is None
    assert Character.objects.not_archived().filter(pk=character.pk).exists()
