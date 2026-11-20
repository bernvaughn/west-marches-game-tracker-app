"""Tests for the open-container view (slice B)."""

import pytest
from django.test import Client
from django.urls import reverse

from items.models import ContainerOpening, Item
from items.opening import open_container
from items.tests.factories import add_slot, make_container
from ledger.models import LedgerEntry
from ledger.services import Line, item_quantities, recent_changes, record

pytestmark = pytest.mark.django_db


def open_url(club, character, item):
    return reverse(
        "characters:open_container",
        kwargs={"club_slug": club.slug, "pk": character.pk, "item_pk": item.pk},
    )


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def award(character, item, quantity=1, actor=None):
    return record(character, "award", [Line(item=item, quantity=quantity)], actor=actor)


def fixed_container(club, name="Pack", item_name="Rope"):
    container = make_container(club, name=name)
    item = Item.objects.create(club=club, name=item_name, value_cp=1)
    add_slot(container, [(item, 1, 1, 1)], chance_pct=100)
    return container, item


def assert_no_raw_template_syntax(content):
    """Catch template tags or comments that Django printed as text."""
    for token in ("{%", "%}", "{#", "#}", "{{", "}}"):
        assert token not in content, f"raw template syntax {token!r} in response"


# ---------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["player", "game_master", "club_admin"])
def test_owner_gm_and_club_admin_can_open(request, login, club, character, who):
    user = request.getfixturevalue(who)
    container, _ = fixed_container(club)
    award(character, container, actor=user)
    r = login(user).post(open_url(club, character, container))
    assert r.status_code == 200
    assert LedgerEntry.objects.filter(kind="opened").count() == 1
    assert ContainerOpening.objects.count() == 1


def test_other_player_forbidden(login, player, club, character, club_admin, other_player):
    container, _ = fixed_container(club)
    award(character, container, actor=club_admin)
    r = login(other_player).post(open_url(club, character, container))
    assert r.status_code == 403
    assert LedgerEntry.objects.filter(kind="opened").count() == 0


def test_other_club_member_gets_404(login, club, character, foreign_member, club_admin):
    container, _ = fixed_container(club)
    award(character, container, actor=club_admin)
    r = login(foreign_member).post(open_url(club, character, container))
    assert r.status_code == 404


def test_anonymous_redirects_to_login(club, character, club_admin):
    container, _ = fixed_container(club)
    award(character, container, actor=club_admin)
    r = Client().post(open_url(club, character, container))
    assert r.status_code == 302
    assert r.url.startswith("/accounts/login/")


def test_get_returns_405(login, player, club, character, club_admin):
    container, _ = fixed_container(club)
    award(character, container, actor=club_admin)
    r = login(player).get(open_url(club, character, container))
    assert r.status_code == 405


def test_non_container_item_returns_404(login, player, club, character, item):
    r = login(player).post(open_url(club, character, item))
    assert r.status_code == 404


def test_character_in_other_club_returns_404(
    login, player, club, foreign_character, club_admin, other_club
):
    container, _ = fixed_container(other_club)
    award(foreign_character, container, actor=club_admin)
    r = login(player).post(open_url(club, foreign_character, container))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# result display
# ---------------------------------------------------------------------------


def test_owner_htmx_open_shows_result(login, player, club, character, club_admin):
    container, rope = fixed_container(club)
    award(character, container, actor=club_admin)
    r = login(player).post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    content = r.content.decode()
    assert "data-wm-reveal" in content
    assert "data-wm-reveal-item" in content
    assert f"+1 {rope.name}" in content
    assert_no_raw_template_syntax(content)
    assert LedgerEntry.objects.filter(kind="opened").count() == 1
    assert ContainerOpening.objects.count() == 1


def test_owner_plain_open_shows_result(login, player, club, character, club_admin):
    container, rope = fixed_container(club)
    award(character, container, actor=club_admin)
    r = login(player).post(open_url(club, character, container))
    assert r.status_code == 200
    content = r.content.decode()
    assert "data-wm-reveal" in content
    assert "data-wm-reveal-item" in content
    assert rope.name in content
    assert_no_raw_template_syntax(content)
    assert content.count('class="wm-card"') == 1
    assert LedgerEntry.objects.filter(kind="opened").count() == 1
    assert ContainerOpening.objects.count() == 1


def test_double_post_fails_without_change(login, player, club, character, club_admin):
    container, _ = fixed_container(club)
    award(character, container, actor=club_admin)
    c = login(player)
    r = c.post(open_url(club, character, container))
    assert r.status_code == 200
    assert LedgerEntry.objects.filter(kind="opened").count() == 1
    assert ContainerOpening.objects.count() == 1
    assert container.pk not in item_quantities(character)

    r = c.post(open_url(club, character, container))
    assert r.status_code == 302  # OpenError -> redirect to sheet
    assert LedgerEntry.objects.filter(kind="opened").count() == 1
    assert ContainerOpening.objects.count() == 1
    assert container.pk not in item_quantities(character)


def test_double_post_htmx_shows_error_without_change(login, player, club, character, club_admin):
    container, _ = fixed_container(club)
    award(character, container, actor=club_admin)
    c = login(player)
    r = c.post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    r = c.post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "has no" in r.content.decode() and container.name in r.content.decode()
    assert_no_raw_template_syntax(r.content.decode())
    # The modal shows the error; no flash message is queued for the next page.
    assert "has no" not in c.get(detail_url(club, character)).content.decode()
    assert LedgerEntry.objects.filter(kind="opened").count() == 1
    assert ContainerOpening.objects.count() == 1


def test_gm_and_club_admin_see_result_for_players_container(
    login, club, character, game_master, club_admin, player
):
    for who in [game_master, club_admin]:
        container, _ = fixed_container(club)
        award(character, container, actor=club_admin)
        r = login(who).post(open_url(club, character, container), HTTP_HX_REQUEST="true")
        assert r.status_code == 200, who
        assert "data-wm-reveal-item" in r.content.decode()


def test_masked_item_name_appears_after_opening_only(login, player, club, character, club_admin):
    letter = Item.objects.create(club=club, name="Sealed letter", value_cp=1)
    container = make_container(club, name="Mystery Box")
    add_slot(container, [(letter, 1, 1, 1)], chance_pct=100, unknown=True)
    award(character, container, actor=club_admin)

    # Pre-open: the sheet/inventory never shows slot contents.
    r = login(player).get(detail_url(club, character))
    assert r.status_code == 200
    assert "Sealed letter" not in r.content.decode()

    # After opening: the result shows the real rolled item.
    r = login(player).post(open_url(club, character, container), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "Sealed letter" in r.content.decode()
    assert "data-wm-reveal-item" in r.content.decode()


# ---------------------------------------------------------------------------
# inventory button and shop pages
# ---------------------------------------------------------------------------


def test_sheet_open_button_for_owner_only(login, player, club, character, other_player, club_admin):
    container, _ = fixed_container(club)
    rope = Item.objects.create(club=club, name="Rope", value_cp=1)
    award(character, container, actor=club_admin)
    award(character, rope, actor=club_admin)

    r = login(player).get(detail_url(club, character))
    assert r.status_code == 200
    content = r.content.decode()
    assert open_url(club, character, container) in content
    assert 'data-wm-tooltip title="Open this container' in content
    assert open_url(club, character, rope) not in content

    r = login(other_player).get(detail_url(club, character))
    assert r.status_code == 200
    assert open_url(club, character, container) not in r.content.decode()


def test_shop_pages_show_no_open_button(login, player, club, character, club_admin):
    container, _ = fixed_container(club)
    award(character, container, actor=club_admin)

    r = login(player).get(
        reverse("shops:player_shop", kwargs={"club_slug": club.slug, "character_id": character.pk})
    )
    assert r.status_code == 200
    assert "open_container" not in r.content.decode()
    assert (
        reverse(
            "characters:open_container",
            kwargs={
                "club_slug": club.slug,
                "pk": character.pk,
                "item_pk": container.pk,
            },
        )
        not in r.content.decode()
    )


# ---------------------------------------------------------------------------
# history and recent changes
# ---------------------------------------------------------------------------


def test_history_shows_opened_entry(login, player, club, character, club_admin):
    container, rope = fixed_container(club)
    award(character, container, actor=club_admin)
    open_container(character, container, club_admin)

    r = login(player).get(
        reverse(
            "ledger:character_history",
            kwargs={
                "club_slug": club.slug,
                "pk": character.pk,
            },
        )
    )
    assert r.status_code == 200
    content = r.content.decode()
    assert "Opened" in content
    assert container.name in content
    assert f"+1 {rope.name}" in content


def test_recent_changes_includes_opened(club, character, club_admin):
    container, rope = fixed_container(club)
    award(character, container, actor=club_admin)
    open_container(character, container, club_admin)

    kinds = [e.kind for e in recent_changes(character)]
    assert "opened" in kinds
