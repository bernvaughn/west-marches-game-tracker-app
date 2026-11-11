from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from ledger.services import Line, record

pytestmark = pytest.mark.django_db


def url(club, character):
    return reverse("characters:print_items", args=[club.slug, character.pk])


@pytest.mark.story("U6")
def test_owner_sees_item_fields(login, club, player, funded, item):
    item.description = "A sturdy rope"
    item.traits = "Flammable"
    item.details = "Fifty feet long"
    item.save()
    r = login(player).get(url(club, funded))
    assert r.status_code == 200
    body = r.content.decode()
    for text in (item.name, "Quantity: 5", "A sturdy rope", "Flammable", "Fifty feet long"):
        assert text in body
    assert "Coins:" in body


@pytest.mark.story("U6")
@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_viewers_get_200(request, login, club, funded, who):
    r = login(request.getfixturevalue(who)).get(url(club, funded))
    assert r.status_code == 200


@pytest.mark.story("U6")
def test_other_player_forbidden(login, club, other_player, funded):
    assert login(other_player).get(url(club, funded)).status_code == 403


@pytest.mark.story("U6")
def test_cross_club_404(login, club, other_club, player, foreign_member, foreign_character):
    assert login(player).get(url(club, foreign_character)).status_code == 404
    assert login(player).get(url(other_club, foreign_character)).status_code == 404


@pytest.mark.story("U6")
def test_zero_quantity_hidden(login, club, player, funded, second_item):
    record(funded, "award", [Line(item=second_item, quantity=2)])
    record(funded, "consumed", [Line(item=second_item, quantity=-2)])
    r = login(player).get(url(club, funded))
    assert second_item.name not in r.content.decode()


@pytest.mark.story("U6")
def test_held_items_still_shown(login, club, player, funded, item, make_open_trade):
    make_open_trade(items={item: 2})
    body = login(player).get(url(club, funded)).content.decode()
    assert item.name in body
    assert "Quantity: 5" in body


@pytest.mark.story("U6")
def test_print_button_and_css(login, club, player, funded):
    body = login(player).get(url(club, funded)).content.decode()
    assert "window.print()" in body
    css = (Path(settings.BASE_DIR) / "static/css/print.css").read_text()
    assert "/* Characters: print view */" in css
