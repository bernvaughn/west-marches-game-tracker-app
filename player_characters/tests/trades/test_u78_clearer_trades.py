import re

import pytest
from django.urls import reverse

from ledger.services import Line
from player_characters import trade_services
from player_characters.trade_status_line import trade_status_line

pytestmark = pytest.mark.story("U78")


def url(club, trade, name="detail"):
    return reverse(f"trades:{name}", args=[club.slug, trade.pk])


@pytest.fixture
def stocked(character, other_character, item, give):
    give(character, item, 5, 1000)
    give(other_character, item, 5, 500)


@pytest.fixture
def requested(stocked, character, other_character, make_trade):
    return make_trade(character, other_character, status="requested")


@pytest.fixture
def accepted(stocked, character, other_character, item, make_trade):
    return make_trade(
        character,
        other_character,
        lines=[(True, Line(item=item, quantity=1))],
        status="accepted",
    )


def html(login, user, club, trade, name="detail"):
    resp = login(user).get(url(club, trade, name))
    assert resp.status_code == 200
    return resp.content.decode()


def test_requested_buttons(login, club, requested, player, other_player):
    mine = html(login, player, club, requested)
    assert "Cancel this trade" in mine and "Accept trade request" not in mine
    theirs = html(login, other_player, club, requested)
    assert "Accept trade request and propose items" in theirs
    assert "Decline this trade request" in theirs
    for old in ("Accept as", "Decline as", "Cancel trade as"):
        assert old not in mine + theirs


def test_accepted_buttons(login, club, accepted, player):
    page = html(login, player, club, accepted)
    assert "Change what you give" in page
    assert "Approve the trade as shown above" in page
    assert "Approve as" not in page and "Edit my side" not in page


def test_accept_leads_to_edit_side(login, club, requested, other_player):
    r = login(other_player).post(url(club, requested, "accept"))
    assert r.status_code == 302 and r.url == url(club, requested, "edit_side")
    requested.refresh_from_db()
    assert requested.status == "accepted"


def test_accept_error_stays_on_detail(login, club, requested, player):
    r = login(player).post(url(club, requested, "accept"))
    assert r.url == url(club, requested)


def line(login, user, club, trade):
    return html(login, user, club, trade).split('role="status">')[1].split("</p>")[0]


def test_status_requested(login, club, requested, player, other_player):
    assert line(login, other_player, club, requested) == (
        f"{player.display_name} wants to trade with Bram. "
        "Accept to choose what you give, or decline."
    )
    assert line(login, player, club, requested) == (
        f"Waiting for {other_player.display_name} to accept."
    )


def test_status_accepted_stages(login, club, accepted, player, other_player):
    assert line(login, player, club, accepted).startswith("Both sides can change")
    login(player).post(url(club, accepted, "approve"))
    assert line(login, player, club, accepted) == (
        f"You have approved. Waiting for {other_player.display_name} to approve as well."
    )
    assert line(login, other_player, club, accepted) == (
        f"{player.display_name} has approved. Approve to complete the trade."
    )


@pytest.mark.parametrize("status", ["completed", "declined", "cancelled"])
def test_status_closed(accepted, status):
    accepted.status = status
    accepted.save()
    accepted.refresh_from_db()
    text = trade_status_line(accepted, "sender")
    assert text.startswith(f"This trade was {status} on ") and text.endswith(".")


def test_status_observer(accepted, game_master):
    assert trade_status_line(accepted, None).startswith("Both sides can change")
    accepted.sender_approved = True
    assert "has approved. Waiting for" in trade_status_line(accepted, None)
    accepted.status = "requested"
    assert trade_status_line(accepted, None).startswith("Waiting for")


def test_status_line_above_sides(login, club, accepted, player):
    page = html(login, player, club, accepted)
    assert page.index("wm-trade-status-line") < page.index("wm-trade-sides")


def test_change_clears_approvals_and_names_changer(
    login, club, accepted, character, other_character, item, player, other_player
):
    trade_services.approve_trade(accepted, "sender", player)
    accepted.refresh_from_db()
    assert accepted.sender_approved
    trade_services.set_side(accepted, "receiver", [Line(item=item, quantity=2)], other_player)
    accepted.refresh_from_db()
    assert not accepted.sender_approved and not accepted.receiver_approved
    assert accepted.sides_changed_by == "receiver"
    assert line(login, player, club, accepted) == (
        f"{other_player.display_name} changed their side. Both of you need to approve again."
    )
    assert line(login, other_player, club, accepted) == (
        "You changed your side. Both of you need to approve again."
    )
    login(player).post(url(club, accepted, "approve"))
    accepted.refresh_from_db()
    assert accepted.sides_changed_by == ""
    assert "changed" not in line(login, player, club, accepted)


def test_sender_change_marks_sender(accepted, item, player):
    trade_services.set_side(accepted, "sender", [Line(item=item, quantity=3)], player)
    accepted.refresh_from_db()
    assert accepted.sides_changed_by == "sender"


def test_unchanged_lines_leave_marker(accepted, item, player):
    trade_services.set_side(accepted, "sender", [Line(item=item, quantity=1)], player)
    accepted.refresh_from_db()
    assert accepted.sides_changed_by == ""


def test_edit_side_sheet_look(login, club, accepted, player, item):
    page = html(login, player, club, accepted, "edit_side")
    for marker in ("wm-sheet-header", "wm-sheet-coins", "wm-sheet-table", "Give"):
        assert marker in page
    assert "Saving a change clears both approvals." in page
    assert 'name="coins_gp"' in page or "coins" in page


def test_edit_side_available_excludes_own_hold(login, club, accepted, player, item):
    # 5 owned, 1 held by this trade: Available shows 5, not 4.
    page = html(login, player, club, accepted, "edit_side")
    assert '<td class="num">5</td>' in page
    assert '<td class="num">4</td>' not in page


def test_propose_shows_note_and_coins_once(login, club, player, character, give, item):
    give(character, item, 5, 1000)
    page = login(player).get(reverse("trades:propose", args=[club.slug])).content.decode()
    visible = re.sub(r'<label class="visually-hidden".*?</label>', "", page, flags=re.S)
    assert visible.count(">Note<") == 1
    assert page.count("Available:") == 1
    assert "available)" not in page.split("wm-sheet-coins")[1].split("</section>")[0]
    assert "Coins to give" in page


def test_cross_club_404(client, club, accepted, foreign_character):
    owner = foreign_character.owner.user
    client.force_login(owner)
    assert client.get(url(club, accepted)).status_code == 404
    assert client.get(url(club, accepted, "edit_side")).status_code == 404
