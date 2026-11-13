import pytest

from player_characters.tests.characters.test_sheet import u


@pytest.fixture
def sheet(funded):
    return funded


@pytest.mark.story("U56")
def test_no_holds_no_line_or_column(club, login, player, sheet):
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert "In open trades" not in html and "Held" not in html


@pytest.mark.story("U56")
def test_coin_hold_links_to_trades(club, login, player, sheet, make_open_trade):
    make_open_trade(coins=100)
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert "In open trades" in html and "Held" not in html
    assert f'href="/c/{club.slug}/trades/' in html or "trades" in html


@pytest.mark.story("U56")
def test_item_hold_shows_column(club, login, player, sheet, item, make_open_trade):
    make_open_trade(items={item: 1})
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert '<th class="num">In open trades</th>' in html


@pytest.mark.story("U59")
def test_row_actions_are_icon_buttons(club, login, player, sheet):
    html = login(player).get(u("characters:detail", club, sheet.pk)).content.decode()
    assert html.count("wm-row-actions btn-group") == 1
    for label in ("Mark as junk", "Print card"):
        assert f'aria-label="{label}"' in html and f'title="{label}"' in html
    # The top-bar shortcuts (U60) carry the attribute too; count the page body only.
    assert (
        html[html.index("<main") :].count("data-wm-tooltip") == 3
    )  # row buttons + Print slip (U70)
    assert "#tag" in html and "#printer" in html
    assert "layout=full" in html and "layout=grid" in html
    assert "js/tooltips.js" in html
