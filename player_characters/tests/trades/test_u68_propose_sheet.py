import pytest
from django.urls import reverse

from ledger.services import Line
from player_characters.models import Trade

pytestmark = pytest.mark.story("U68")


def url(club):
    return reverse("trades:propose", args=[club.slug])


@pytest.fixture
def stocked(character, item, give):
    give(character, item, 5, 1000)
    return character


def page(login, player, club, query=""):
    resp = login(player).get(url(club) + query)
    assert resp.status_code == 200
    return resp.content.decode()


def test_header_box_and_preselect(login, player, club, stocked, other_character):
    html = page(login, player, club, f"?to={other_character.pk}")
    assert "wm-page-header" in html
    assert f"From {stocked.name}" in html
    assert f'<option value="{other_character.pk}" selected' in html


def test_coins_box_owned_and_available(login, player, club, stocked, other_character, make_trade):
    make_trade(stocked, other_character, [(True, Line(coins=300))], status="requested")
    html = page(login, player, club)
    assert "Available:" in html
    assert 'name="offer-coins_gp"' in html


def test_inventory_table_and_disabled_row(
    login, player, club, stocked, other_character, item, make_trade
):
    html = page(login, player, club)
    assert f'name="offer-item_{item.pk}"' in html
    assert '<th class="num">Offer</th>' in html
    assert "wm-trade-row-unavailable" not in html
    make_trade(stocked, other_character, [(True, Line(item=item, quantity=5))])
    html = page(login, player, club)
    assert "wm-trade-row-unavailable" in html
    assert f'name="offer-item_{item.pk}"' not in html
    assert "disabled" in html


def test_note_box_and_button_after_boxes(login, player, club, stocked):
    html = page(login, player, club)
    assert "wm-sheet-grid" in html
    assert 'name="note"' in html
    assert html.index('name="note"') < html.index("Propose trade as")
    assert html.index("offer-items-title") < html.index("Propose trade as")


def test_propose_and_validation(login, player, club, stocked, other_character, item):
    client = login(player)
    bad = client.post(
        url(club),
        {"receiver": other_character.pk, "note": "", f"offer-item_{item.pk}": 99},
    )
    assert bad.status_code == 200
    assert Trade.objects.count() == 0
    ok = client.post(
        url(club),
        {"receiver": other_character.pk, "note": "hi", f"offer-item_{item.pk}": 2},
    )
    assert ok.status_code == 302
    assert Trade.objects.count() == 1


def test_foreign_to_is_404(login, player, club, stocked, foreign_character):
    resp = login(player).get(url(club) + f"?to={foreign_character.pk}")
    assert resp.status_code == 404
