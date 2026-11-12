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


def item_url(club, character, item):
    return reverse("characters:print_item", args=[club.slug, character.pk, item.pk])


def many_items(club, character, n):
    from items.models import Item

    items = [Item.objects.create(club=club, name=f"Thing {i:02d}", value_cp=1) for i in range(n)]
    record(character, "award", [Line(item=i, quantity=1) for i in items])
    return items


@pytest.mark.story("U40")
def test_print_all_nine_per_sheet(login, club, player, funded):
    many_items(club, funded, 9)  # 10 items with the fixture item
    r = login(player).get(url(club, funded))
    body = r.content.decode()
    assert body.count('class="wm-item-card"') == 10
    assert body.count('<section class="wm-card-sheet">') == 2
    first = body.split('<section class="wm-card-sheet">')[1]
    assert first.count('class="wm-item-card"') == 9
    assert "player_characters/characters/_item_card.html" in [t.name for t in r.templates]


@pytest.mark.story("U40")
def test_card_css():
    base = Path(settings.BASE_DIR) / "static/css"
    css = (base / "print.css").read_text()
    assert "size: portrait" in css and "break-after: page" in css
    cards = (base / "areas/characters.css").read_text()
    assert "2.5in" in cards and "3.5in" in cards


@pytest.mark.story("U40")
def test_print_item_layouts(login, club, player, funded, item):
    c = login(player)
    full = c.get(item_url(club, funded, item), {"layout": "full"})
    assert full.status_code == 200
    assert "wm-item-card--full" in full.content.decode()
    assert "player_characters/characters/_item_card.html" in [t.name for t in full.templates]
    grid = c.get(item_url(club, funded, item), {"layout": "grid"}).content.decode()
    assert grid.count('class="wm-item-card"') == 1
    assert grid.count("wm-card-cell") == 8
    assert c.get(item_url(club, funded, item), {"layout": "bogus"}).status_code == 400
    choose = c.get(item_url(club, funded, item)).content.decode()
    assert "?layout=full" in choose and "?layout=grid" in choose


@pytest.mark.story("U40")
@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin"])
def test_print_item_viewers(request, login, club, funded, item, who):
    u = request.getfixturevalue(who)
    assert login(u).get(item_url(club, funded, item), {"layout": "grid"}).status_code == 200


@pytest.mark.story("U40")
def test_print_item_refusals(
    login,
    club,
    other_club,
    player,
    other_player,
    funded,
    item,
    second_item,
    foreign_member,
    foreign_character,
    foreign_item,
    other_character,
):
    assert login(other_player).get(item_url(club, funded, item)).status_code == 403
    c = login(player)
    assert c.get(item_url(club, foreign_character, item)).status_code == 404
    assert c.get(item_url(other_club, foreign_character, item)).status_code == 404
    assert c.get(item_url(club, funded, foreign_item)).status_code == 404
    assert c.get(item_url(club, funded, second_item)).status_code == 404  # not owned
    record(funded, "award", [Line(item=second_item, quantity=1)])
    record(funded, "consumed", [Line(item=second_item, quantity=-1)])
    assert c.get(item_url(club, funded, second_item)).status_code == 404  # zero quantity


@pytest.mark.story("U40")
def test_sheet_has_print_card_links(login, club, player, funded, item):
    body = (
        login(player)
        .get(reverse("characters:detail", args=[club.slug, funded.pk]))
        .content.decode()
    )
    base = item_url(club, funded, item)
    assert "Print card" in body
    assert f"{base}?layout=full" in body and f"{base}?layout=grid" in body


@pytest.mark.story("U40")
def test_card_pages_drop_main_padding_in_print(login, club, player, funded, item):
    # Letter's page area is about 10.5 in, the sheet height: padding pushes row 3 over.
    c = login(player)
    for r in (c.get(url(club, funded)), c.get(item_url(club, funded, item), {"layout": "grid"})):
        assert 'class="wm-main wm-card-print"' in r.content.decode()
    css = (Path(settings.BASE_DIR) / "static/css/print.css").read_text()
    assert ".wm-card-print { padding: 0" in css
