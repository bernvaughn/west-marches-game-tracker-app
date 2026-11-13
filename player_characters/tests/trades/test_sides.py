import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import Membership, User
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import Line, coin_balance, item_quantities
from player_characters import trade_services
from player_characters.models import Trade

pytestmark = pytest.mark.story("U16")


def url(club, trade, name="edit_side"):
    return reverse(f"trades:{name}", args=[club.slug, trade.pk])


def msgs(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


@pytest.fixture
def trade(character, other_character, item, give, make_trade):
    give(character, item, 5, 1000)
    give(other_character, None, 0, 500)
    return make_trade(
        character,
        other_character,
        lines=[(True, Line(item=item, quantity=2))],
        status="accepted",
    )


def test_get_form_lists_own_items_only(login, club, trade, other_player, character, item):
    other = Item.objects.create(club=club, name="Hidden Lamp", value_cp=1)
    from ledger.services import record

    record(character, "award", [Line(item=other, quantity=1)], note="x")
    html = login(other_player).get(url(club, trade)).content.decode()
    assert "Rope" not in html and "Hidden Lamp" not in html
    assert "No items." in html
    assert "coins_gp" in html


def test_get_form_initial_and_exclude_trade(login, club, trade, player):
    r = login(player).get(url(club, trade))
    html = r.content.decode()
    assert r.status_code == 200
    assert "Rope (5 available)" in html
    assert f'name="item_{trade.lines.first().item_id}"' in html
    assert 'value="2"' in html


def test_other_open_trade_hold_not_offered(
    login, club, trade, player, character, item, other_character, make_trade
):
    make_trade(character, other_character, lines=[(True, Line(item=item, quantity=2))])
    html = login(player).get(url(club, trade)).content.decode()
    assert "Rope (3 available)" in html  # 5 minus the 2 held by the other trade
    assert "Rope (5 available)" not in html
    c = login(player)
    key = f"item_{item.pk}"
    r = c.post(url(club, trade), {key: 4})
    assert r.status_code == 200
    assert trade.lines.get().quantity == 2


def test_post_changed_clears_approvals(login, club, trade, player, item):
    Trade.objects.filter(pk=trade.pk).update(receiver_approved=True)
    r = login(player).post(url(club, trade), {f"item_{item.pk}": 3})
    assert r.status_code == 302
    trade.refresh_from_db()
    assert trade.lines.get().quantity == 3
    assert not trade.receiver_approved and not trade.sender_approved


def test_post_unchanged_keeps_approvals(login, club, trade, player, item):
    Trade.objects.filter(pk=trade.pk).update(receiver_approved=True)
    r = login(player).post(url(club, trade), {f"item_{item.pk}": 2})
    assert r.status_code == 302
    trade.refresh_from_db()
    assert trade.receiver_approved


def test_receiver_adds_coins(login, club, trade, other_player):
    r = login(other_player).post(url(club, trade), {"coins_gp": 3})
    assert r.status_code == 302
    assert trade.lines.get(from_sender=False).coins == 300


def test_post_over_limit_rejected(login, club, trade, other_player):
    r = login(other_player).post(url(club, trade), {"coins_gp": 99})
    assert r.status_code == 200
    assert not trade.lines.filter(from_sender=False).exists()


def test_edit_refused_requested(login, club, trade, player, item):
    Trade.objects.filter(pk=trade.pk).update(status="requested")
    c = login(player)
    r = c.get(url(club, trade))
    assert r.status_code == 302 and msgs(r)
    r = c.post(url(club, trade), {f"item_{item.pk}": 4})
    assert r.status_code == 302 and msgs(r)
    assert trade.lines.get().quantity == 2


def test_edit_refused_after_own_approval(login, club, trade, player, item):
    Trade.objects.filter(pk=trade.pk).update(sender_approved=True)
    c = login(player)
    assert c.get(url(club, trade)).status_code == 302
    r = c.post(url(club, trade), {f"item_{item.pk}": 4})
    assert r.status_code == 302 and msgs(r)
    assert trade.lines.get().quantity == 2


def test_edit_refused_completed(login, club, trade, player, item):
    Trade.objects.filter(pk=trade.pk).update(status="completed")
    c = login(player)
    assert c.get(url(club, trade)).status_code == 302
    r = c.post(url(club, trade), {f"item_{item.pk}": 4})
    assert r.status_code == 302
    assert trade.lines.get().quantity == 2


@pytest.mark.parametrize("name", ["edit_side", "approve"])
def test_non_party_404(login, club, trade, name):
    u = User.objects.create_user("x@example.com", password="pw", display_name="X")
    Membership.objects.create(user=u, club=club)
    c = login(u)
    assert c.post(url(club, trade, name)).status_code == 404
    assert c.get(url(club, trade, "edit_side")).status_code == 404


@pytest.mark.parametrize("who", ["game_master", "club_admin"])
@pytest.mark.parametrize("name", ["edit_side", "approve"])
def test_viewer_403(request, login, club, trade, who, name):
    c = login(request.getfixturevalue(who))
    assert c.post(url(club, trade, name)).status_code == 403
    assert c.get(url(club, trade, "edit_side")).status_code == 403


def test_foreign_user_blocked(login, club, trade, foreign_character):
    c = login(foreign_character.owner.user)
    assert c.get(url(club, trade)).status_code in (403, 404)
    assert c.post(url(club, trade, "approve")).status_code in (403, 404)


def test_cross_club_pk_404(login, club, other_club, foreign_character, make_trade, player):
    u2 = User.objects.create_user("y@example.com", password="pw", display_name="Y")
    m = Membership.objects.create(user=u2, club=other_club)
    from player_characters.models import Character

    c2 = Character.objects.create(club=other_club, owner=m, name="Q")
    t = make_trade(foreign_character, c2, status="accepted")
    assert login(player).get(url(club, t)).status_code == 404
    assert login(player).post(url(club, t, "approve")).status_code == 404


def test_approve_sets_own_flag_only(login, club, trade, player):
    r = login(player).post(url(club, trade, "approve"))
    assert r.status_code == 302
    trade.refresh_from_db()
    assert trade.sender_approved and not trade.receiver_approved
    assert trade.status == "accepted"


def test_approve_twice_errors(login, club, trade, player):
    c = login(player)
    c.post(url(club, trade, "approve"))
    r = c.post(url(club, trade, "approve"))
    assert r.status_code == 302 and msgs(r)


def test_approve_requested_errors(login, club, trade, player):
    Trade.objects.filter(pk=trade.pk).update(status="requested")
    r = login(player).post(url(club, trade, "approve"))
    trade.refresh_from_db()
    assert msgs(r) and not trade.sender_approved


def test_approve_no_lines_errors(login, club, character, other_character, make_trade, player):
    t = make_trade(character, other_character, status="accepted")
    r = login(player).post(url(club, t, "approve"))
    t.refresh_from_db()
    assert msgs(r) and not t.sender_approved


def test_get_approve_not_allowed(login, club, trade, player):
    assert login(player).get(url(club, trade, "approve")).status_code == 405


def test_side_actions_shown_then_hidden(login, club, trade, player, game_master):
    html = login(player).get(url(club, trade, "detail")).content.decode()
    assert "Change what you give" in html and "Approve the trade as shown above" in html
    html = login(game_master).get(url(club, trade, "detail")).content.decode()
    assert "Change what you give" not in html and "Approve the trade as shown above" not in html
    login(player).post(url(club, trade, "approve"))
    html = login(player).get(url(club, trade, "detail")).content.decode()
    assert "Change what you give" not in html and "Approve the trade as shown above" not in html
    assert (
        "You have approved. Waiting for Bram's player to approve as well." in html
        or "to approve as well." in html
    )


def test_completed_note(login, club, trade, player, game_master):
    Trade.objects.filter(pk=trade.pk).update(status="completed")
    for u in (player, game_master):
        html = login(u).get(url(club, trade, "detail")).content.decode()
        assert "This trade was completed on" in html


def test_full_flow(login, club, character, other_character, item, give, player, other_player):
    give(character, item, 4, 0)
    give(other_character, None, 0, 1000)
    trade = trade_services.propose_trade(
        character, other_character, [Line(item=item, quantity=2)], "swap", player
    )
    trade_services.accept_trade(trade, other_player)
    rc = login(other_player)
    assert rc.post(url(club, trade), {"coins_gp": 5}).status_code == 302
    assert rc.post(url(club, trade, "approve")).status_code == 302
    r = login(player).post(url(club, trade, "approve"))
    assert "Trade completed." in msgs(r)
    trade.refresh_from_db()
    assert trade.status == "completed"
    entries = LedgerEntry.objects.filter(kind="trade")
    assert entries.count() == 2
    assert {e.character_id for e in entries} == {character.pk, other_character.pk}
    assert item_quantities(character).get(item.pk) == 2
    assert item_quantities(other_character).get(item.pk) == 2
    assert coin_balance(character) == 500
    assert coin_balance(other_character) == 500
