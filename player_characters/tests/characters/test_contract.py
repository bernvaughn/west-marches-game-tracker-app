import pytest
from django.core.exceptions import PermissionDenied
from django.urls import resolve, reverse

from items.models import Item
from ledger.services import Line, record
from player_characters.access import (
    can_edit_character,
    owns_character,
    require_inventory_access,
)
from player_characters.forms import formset_lines, item_line_formset
from player_characters.inventory import coin_summary, inventory_rows

PK_ROUTES = {
    "characters:detail": "player_characters.views.characters",
    "characters:edit": "player_characters.views.characters",
    "characters:handover": "player_characters.views.characters",
    "characters:adjust": "player_characters.views.character_adjust",
    "characters:consume": "player_characters.views.character_adjust",
    "characters:transfer": "player_characters.views.character_transfer",
    "characters:print_items": "player_characters.views.character_print",
    "ledger:character_history": "ledger.views",
}
PLAIN_ROUTES = {
    "characters:index": "player_characters.views.characters",
    "characters:create": "player_characters.views.characters",
    "characters:directory": "player_characters.views.characters",
}


def url(name, club, pk=None):
    kwargs = {"club_slug": club.slug}
    if pk is not None:
        kwargs["pk"] = pk
    return reverse(name, kwargs=kwargs)


@pytest.mark.parametrize("name,module", {**PK_ROUTES, **PLAIN_ROUTES}.items())
def test_routes_resolve_to_module(club, name, module):
    pk = 1 if name in PK_ROUTES else None
    assert resolve(url(name, club, pk)).func.__module__ == module


# (route, user fixture name, expected status); the character is owned by `player`.
MATRIX = [
    *[
        (n, u, 200)
        for n in ("characters:directory", "characters:create")
        for u in ("player", "game_master", "site_admin")
    ],
    ("characters:index", "player", 403),
    ("characters:index", "game_master", 200),
    ("characters:index", "site_admin", 200),
    ("characters:detail", "player", 200),
    ("characters:detail", "other_player", 200),
    *[("characters:edit", u, 200) for u in ("player", "game_master", "club_admin", "site_admin")],
    ("characters:edit", "other_player", 403),
    ("characters:handover", "club_admin", 200),
    ("characters:handover", "site_admin", 200),
    ("characters:handover", "game_master", 403),
    ("characters:handover", "player", 403),
    *[
        (n, u, 200)
        for n in ("characters:adjust", "characters:consume")
        for u in ("game_master", "club_admin", "site_admin")
    ],
    *[(n, "player", 403) for n in ("characters:adjust", "characters:consume")],
    ("characters:transfer", "player", 200),
    *[
        ("characters:transfer", u, 403)
        for u in ("game_master", "club_admin", "other_player", "site_admin")
    ],
    *[
        (n, u, 200)
        for n in ("characters:print_items", "ledger:character_history")
        for u in ("player", "game_master", "club_admin", "site_admin")
    ],
    *[(n, "other_player", 403) for n in ("characters:print_items", "ledger:character_history")],
]


@pytest.mark.parametrize("name,who,status", MATRIX)
def test_role_matrix(request, login, club, character, name, who, status):
    user = request.getfixturevalue(who)
    pk = character.pk if name in PK_ROUTES else None
    assert login(user).get(url(name, club, pk)).status_code == status


@pytest.mark.parametrize("name", PK_ROUTES)
@pytest.mark.parametrize("who", ["club_admin", "site_admin"])
def test_foreign_character_is_404(request, login, club, foreign_character, name, who):
    user = request.getfixturevalue(who)
    resp = login(user).get(url(name, club, foreign_character.pk))
    assert resp.status_code == 404


@pytest.mark.parametrize("name", [*PK_ROUTES, *PLAIN_ROUTES])
def test_foreign_member_is_404_in_other_club(login, club, character, foreign_member, name):
    pk = character.pk if name in PK_ROUTES else None
    assert login(foreign_member).get(url(name, club, pk)).status_code == 404


@pytest.mark.parametrize("name", [*PK_ROUTES, *PLAIN_ROUTES])
def test_anonymous_redirects_to_login(client, club, character, name):
    pk = character.pk if name in PK_ROUTES else None
    resp = client.get(url(name, club, pk))
    assert resp.status_code == 302
    assert "login" in resp["Location"]


# helpers


def test_inventory_rows_owned_held_available(funded, item, other_character, make_open_trade):
    make_open_trade(items={item: 2}, coins=300)
    (row,) = inventory_rows(funded)
    assert (row.item, row.owned, row.held, row.available) == (item, 5, 2, 3)
    summary = coin_summary(funded)
    assert (summary.owned, summary.held, summary.available) == (1000, 300, 700)
    assert summary.has_holds


def test_inventory_rows_order_retired_and_zero(funded, item, second_item):
    record(funded, "award", [Line(item=second_item, quantity=2)])
    item.retired = True
    item.save()
    assert [r.item.name for r in inventory_rows(funded)] == ["Rope", "Torch"]
    record(funded, "consumed", [Line(item=second_item, quantity=-2)])
    assert [r.item.name for r in inventory_rows(funded)] == ["Rope"]


def test_inventory_rows_empty(character):
    assert inventory_rows(character) == []


def test_coin_summary_parts(character):
    record(character, "award", [Line(coins=1234)])
    s = coin_summary(character)
    assert s.parts == [("pp", 0), ("gp", 12), ("sp", 3), ("cp", 4)]
    assert not s.has_holds


def test_access_helpers(character, player, other_player, game_master, club_admin, site_admin):
    assert owns_character(player, character)
    assert not owns_character(game_master, character)
    assert not owns_character(site_admin, character)
    for u in (player, game_master, club_admin, site_admin):
        assert can_edit_character(u, character)
        require_inventory_access(u, character)
    assert not can_edit_character(other_player, character)
    with pytest.raises(PermissionDenied):
        require_inventory_access(other_player, character)


def _data(rows, prefix="items"):
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(rows)),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "3",
    }
    for i, (it, qty) in enumerate(rows):
        data[f"{prefix}-{i}-item"] = str(it.pk) if it else ""
        data[f"{prefix}-{i}-quantity"] = str(qty) if qty else ""
    return data


def test_formset_valid_and_lines(club, item, second_item):
    qs = Item.objects.filter(club=club)
    fs = item_line_formset(qs, _data([(item, 2), (None, None), (second_item, 1)]))
    assert fs.is_valid()
    assert formset_lines(fs, 1) == [Line(item=item, quantity=2), Line(item=second_item, quantity=1)]
    assert formset_lines(fs, -1)[0] == Line(item=item, quantity=-2)
    with pytest.raises(ValueError):
        formset_lines(fs, 0)


def test_formset_blank_rows_valid(club):
    fs = item_line_formset(Item.objects.filter(club=club), _data([(None, None)] * 3))
    assert fs.is_valid()
    assert formset_lines(fs, 1) == []


def test_formset_half_row_invalid(club, item):
    qs = Item.objects.filter(club=club)
    assert not item_line_formset(qs, _data([(item, None)])).is_valid()
    assert not item_line_formset(qs, _data([(None, 3)])).is_valid()


def test_formset_foreign_item_invalid(club, foreign_item):
    qs = Item.objects.filter(club=club)
    assert not item_line_formset(qs, _data([(foreign_item, 1)])).is_valid()


def test_formset_duplicate_invalid(club, item):
    fs = item_line_formset(Item.objects.filter(club=club), _data([(item, 1), (item, 2)]))
    assert not fs.is_valid()
    assert "Pick each item once." in fs.non_form_errors()


def test_formset_too_many_rows_invalid(club, item):
    fs = item_line_formset(Item.objects.filter(club=club), _data([(item, 1)] * 4))
    assert not fs.is_valid()
