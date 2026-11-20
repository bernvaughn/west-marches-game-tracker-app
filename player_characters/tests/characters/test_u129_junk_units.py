"""Junk marks by the unit (U129): mark any count up to units owned, for stacked items."""

import pytest
from django.urls import reverse

from items.tests.factories import make_parchment
from ledger.services import Line, record
from player_characters.junk import JunkError, junk_rows, set_junk
from player_characters.models import JunkMark

pytestmark = [pytest.mark.story("U129"), pytest.mark.django_db]


@pytest.fixture
def parchment(club):
    return make_parchment(club)


@pytest.fixture
def owned(character, parchment, player):
    record(character, "award", [Line(item=parchment, quantity=7), Line(coins=100)])
    return character


def junk_url(club, character, item):
    return reverse("characters:junk", args=[club.slug, character.pk, item.pk])


# --- unit count capped at units owned -------------------------------------


def test_any_count_up_to_owned_for_stacked(owned, parchment, player):
    set_junk(owned, parchment, 7, player)
    assert [(r.item, r.quantity) for r in junk_rows(owned)] == [(parchment, 7)]
    set_junk(owned, parchment, 3, player)
    assert junk_rows(owned)[0].quantity == 3


def test_over_owned_refused(owned, parchment, player):
    with pytest.raises(JunkError, match="owns only"):
        set_junk(owned, parchment, 8, player)
    assert junk_rows(owned) == []


def test_error_uses_unit_name(owned, parchment, player):
    with pytest.raises(JunkError, match="7 ft Rope|7 sheet Parchment"):
        set_junk(owned, parchment, 8, player)


def test_zero_clears_the_mark(owned, parchment, player):
    set_junk(owned, parchment, 3, player)
    set_junk(owned, parchment, 0, player)
    assert junk_rows(owned) == []
    assert JunkMark.objects.count() == 0


def test_non_stacked_unchanged(club, character, player, item):
    record(character, "award", [Line(item=item, quantity=5)])
    set_junk(character, item, 3, player)
    assert junk_rows(character)[0].quantity == 3


# --- permissions ----------------------------------------------------------


@pytest.mark.parametrize("who", ["player", "game_master", "club_admin"])
def test_privileged_can_mark(club, login, request, owned, parchment, who):
    r = login(request.getfixturevalue(who)).post(
        junk_url(club, owned, parchment), {"quantity": "2"}
    )
    assert r.status_code == 302
    assert junk_rows(owned)[0].quantity == 2


def test_other_club_character_404(club, login, player, owned, parchment, other_club, other_player):
    from accounts.models import Membership, User

    foreign_user = User.objects.create_user("x@example.com", password="pw", display_name="X")
    foreign_member = Membership.objects.create(user=foreign_user, club=other_club)
    from player_characters.models import Character

    foreign_character = Character.objects.create(club=other_club, owner=foreign_member, name="Zed")
    c = login(player)
    assert c.get(junk_url(club, foreign_character, parchment)).status_code == 404


def test_other_club_item_404(club, login, player, owned, parchment, other_club):
    from items.models import Item

    foreign_item = Item.objects.create(club=other_club, name="Foreign Parchment", value_cp=100)
    c = login(player)
    assert c.get(junk_url(club, owned, foreign_item)).status_code == 404


def test_other_member_forbidden(club, login, other_player, owned, parchment):
    c = login(other_player)
    assert c.get(junk_url(club, owned, parchment)).status_code == 403
    assert c.post(junk_url(club, owned, parchment), {"quantity": "1"}).status_code == 403


# --- view shows unit-aware label and units --------------------------------


def test_junk_view_shows_unit_aware_text(club, login, player, owned, parchment):
    c = login(player)
    body = c.get(junk_url(club, owned, parchment), HTTP_HX_REQUEST="true").content.decode()
    assert "How many sheet are junk?" in body
    assert "owns 7 sheet Parchment" in body


def test_junk_view_shows_normal_text_unchanged(club, login, player, character, item):
    record(character, "award", [Line(item=item, quantity=5)])
    set_junk(character, item, 3, player)
    c = login(player)
    url = reverse("characters:junk", args=[club.slug, character.pk, item.pk])
    body = c.get(url, HTTP_HX_REQUEST="true").content.decode()
    assert "How many are junk?" in body
    assert "owns 5 \u00d7" in body
