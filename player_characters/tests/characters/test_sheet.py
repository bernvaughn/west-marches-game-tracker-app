import pytest
from django.urls import reverse

from player_characters.models import Character


def u(name, club, pk=None):
    kw = {"club_slug": club.slug}
    if pk is not None:
        kw["pk"] = pk
    return reverse(name, kwargs=kw)


@pytest.fixture
def sheet(funded):
    funded.notes = "Secret backstory"
    funded.save()
    return funded


@pytest.mark.story("U8")
def test_coins_split(club, login, player, sheet):
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert "10 gp" in html
    for zero in ("pp: 0", "sp: 0", "cp: 0"):
        assert zero not in html
    assert "Rope" in html
    assert "Held" not in html


@pytest.mark.story("U8")
def test_holds_shown(club, login, player, sheet, make_open_trade):
    make_open_trade(coins=100)
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert "In open trades" in html and "Available" in html


@pytest.mark.story("U19")
def test_other_player_sees_name_and_owner_only(club, login, other_player, sheet):
    r = login(other_player).get(u("characters:detail", club, sheet.pk))
    html = r.content.decode()
    assert r.status_code == 200
    assert "Aria" in html and "Player" in html
    for secret in ("Secret backstory", "Rope", "pp: 1"):
        assert secret not in html
    for name in ("edit", "adjust", "consume", "print_items", "transfer", "handover"):
        assert u(f"characters:{name}", club, sheet.pk) not in html
    assert u("ledger:character_history", club, sheet.pk) not in html


@pytest.mark.story("U19")
@pytest.mark.parametrize("who", ["player", "game_master", "club_admin", "site_admin"])
def test_privileged_see_sheet(club, login, request, sheet, who):
    html = (
        login(request.getfixturevalue(who))
        .get(u("characters:detail", club, sheet.pk))
        .content.decode()
    )
    assert "Secret backstory" in html and "Rope" in html
    assert u("characters:edit", club, sheet.pk) in html
    assert u("characters:print_items", club, sheet.pk) in html
    assert u("ledger:character_history", club, sheet.pk) in html


@pytest.mark.story("U19")
def test_adjust_links_gm_admin_only(club, login, player, game_master, sheet):
    adjust = u("characters:adjust", club, sheet.pk)
    assert adjust not in login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert adjust in login(game_master).get(u("characters:detail", club, sheet.pk)).content.decode()


@pytest.mark.story("U19")
def test_transfer_link_owner_with_two_characters(
    club, login, player, game_master, character, second_character
):
    t = u("characters:transfer", club, character.pk)
    assert t in login(player).get(u("characters:detail", club, character.pk)).content.decode()
    assert (
        t not in login(game_master).get(u("characters:detail", club, character.pk)).content.decode()
    )


@pytest.mark.story("U19")
def test_transfer_link_absent_with_one_character(club, login, player, character):
    html = login(player).get(u("characters:detail", club, character.pk)).content.decode()
    assert u("characters:transfer", club, character.pk) not in html


@pytest.mark.story("U19")
def test_foreign_member_gets_404(club, login, foreign_member, character):
    assert login(foreign_member).get(u("characters:detail", club, character.pk)).status_code == 404
    assert login(foreign_member).get(u("characters:index", club)).status_code in (403, 404)


@pytest.mark.story("U2")
def test_index_lists_all_without_inventory(club, login, other_player, sheet):
    html = login(other_player).get(u("characters:directory", club)).content.decode()
    assert "Aria" in html and "Player" in html and "Rope" not in html
    assert Character.objects.count() == 1


@pytest.mark.story("U37")
def test_sheet_header_and_print_button(club, login, player, sheet):
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert "Played by" in html and club.name in html
    assert "Print sheet" in html and "Recent ledger entries" in html


@pytest.mark.story("U37")
def test_empty_notes_one_line(club, login, player, sheet):
    sheet.notes = ""
    sheet.save()
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert "No notes yet." in html


@pytest.mark.story("U37")
def test_other_player_sees_no_ledger_or_print(club, login, other_player, sheet):
    html = login(other_player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert "Recent ledger entries" not in html and "Print sheet" not in html
