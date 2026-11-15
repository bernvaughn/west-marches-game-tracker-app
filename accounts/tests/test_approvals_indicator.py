import datetime

import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts import approvals
from accounts.approval_providers import open_messages, open_trades_needing_action
from accounts.models import Membership, Message
from agent_access.approvals import pending_batches, pending_proposed_items
from agent_access.models import ProposedBatch, ProposedItem
from agent_access.tokens import create_token
from map.approvals import open_map_requests
from map.models import MapRequest
from player_characters.models import Character, Trade

pytestmark = [pytest.mark.django_db, pytest.mark.story("U26")]


def _req(rf, user, club):
    request = rf.get("/")
    request.user = user
    request.club = club
    request.membership = Membership.objects.filter(user=user, club=club).first()
    return request


def _labels(rf, user, club):
    return {a.label: a.count for a in approvals.pending_approvals(_req(rf, user, club))}


def _seed(
    club,
    user,
    status_batch="pending",
    status_item="pending",
    status_req="requested",
    status_msg="open",
):
    conn, _ = create_token(user, club, f"agent-{club.slug}-{ProposedBatch.objects.count()}")
    ProposedBatch.objects.create(
        club=club,
        connection=conn,
        user=user,
        date=datetime.date.today(),
        idempotency_key=f"k{ProposedBatch.objects.count()}",
        status=status_batch,
    )
    ProposedItem.objects.create(club=club, name="Dagger", status=status_item)
    member = Membership.objects.filter(club=club).first()
    MapRequest.objects.create(club=club, kind="visit", requested_by=member, status=status_req)
    Message.objects.create(club=club, sender=member, body="hi", status=status_msg)


def test_registry_has_real_providers():
    for p in (pending_batches, pending_proposed_items, open_map_requests, open_messages, open_trades_needing_action):
        assert p in approvals._providers


def test_game_master_counts(rf, club, game_master):
    _seed(club, game_master)
    assert _labels(rf, game_master, club) == {
        "Agent batches": 1,
        "Proposed items": 1,
        "Map requests": 1,
    }


def test_club_admin_counts(rf, club, club_admin, game_master):
    _seed(club, game_master)
    assert _labels(rf, club_admin, club) == {
        "Proposed items": 1,
        "Map requests": 1,
        "Messages": 1,
    }


def test_player_sees_nothing_and_no_menu(rf, club, player, game_master, login):
    _seed(club, game_master)
    assert _labels(rf, player, club) == {}
    html = login(player).get(reverse("club_home", args=[club.slug])).content.decode()
    assert "approvals-menu" not in html


def test_zero_hides_menu(club, game_master, login):
    html = login(game_master).get(reverse("club_home", args=[club.slug])).content.decode()
    assert "approvals-menu" not in html


def test_non_pending_not_counted(rf, club, game_master, club_admin):
    _seed(club, game_master, "confirmed", "approved", "declined", "handled")
    assert _labels(rf, game_master, club) == {}
    assert _labels(rf, club_admin, club) == {}


def test_clubs_stay_separate(rf, club, other_club, game_master, club_admin):
    _seed(club, game_master)
    from conftest import _member  # noqa: PLC0415

    other = _member(other_club, "b@example.com", "B", is_club_admin=True, is_game_master=True)
    assert _labels(rf, other, other_club) == {}
    _seed(other_club, other)
    ProposedItem.objects.create(club=other_club, name="Extra")
    assert _labels(rf, other, other_club)["Proposed items"] == 2
    assert _labels(rf, game_master, club)["Proposed items"] == 1


def test_rendered_badge_and_links(club, game_master, login):
    _seed(club, game_master)
    html = login(game_master).get(reverse("club_home", args=[club.slug])).content.decode()
    assert "approvals-menu" in html
    assert 'approvals-total">3<' in html
    for name in ("batches", "proposed_items"):
        assert reverse(f"agent_access:{name}", args=[club.slug]) in html
    assert reverse("map:requests", args=[club.slug]) in html


def test_demo_gwen_badge(login):
    call_command("seed_demo")
    call_command("seed_demo")
    from accounts.models import User

    gwen = User.objects.get(email="gm@example.com")
    html = login(gwen).get("/c/demo/").content.decode()
    assert "approvals-menu" in html
    for label in ("Agent batches", "Proposed items", "Map requests", "Messages"):
        assert label in html
    assert 'approvals-total">5<' in html


def test_trade_requested_receiver_needs_action(rf, club, player, game_master, character):
    # Trade REQUESTED where game_master is receiver - needs to accept/decline
    sender_char = character
    gm_membership = Membership.objects.get(user=game_master, club=club)
    receiver_char = Character.objects.create(club=club, owner=gm_membership, name="GM Char")
    trade = Trade.objects.create(
        club=club,
        sender=sender_char,
        receiver=receiver_char,
        status=Trade.Status.REQUESTED,
    )
    # Receiver (game_master) should see the trade
    assert _labels(rf, game_master, club) == {"Trades": 1}
    # Sender (player) should not see it (not their action needed)
    assert _labels(rf, player, club) == {}
    trade.delete()


def test_trade_accepted_sender_needs_approval(rf, club, player, game_master, character):
    # Trade ACCEPTED where sender hasn't approved
    sender_char = character
    gm_membership = Membership.objects.get(user=game_master, club=club)
    receiver_char = Character.objects.create(club=club, owner=gm_membership, name="GM Char")
    trade = Trade.objects.create(
        club=club,
        sender=sender_char,
        receiver=receiver_char,
        status=Trade.Status.ACCEPTED,
        sender_approved=False,
        receiver_approved=True,
    )
    # Sender (player) needs to approve
    assert _labels(rf, player, club) == {"Trades": 1}
    # Receiver (game_master) already approved
    assert _labels(rf, game_master, club) == {}
    trade.delete()


def test_trade_accepted_receiver_needs_approval(rf, club, player, game_master, character):
    # Trade ACCEPTED where receiver hasn't approved
    sender_char = character
    gm_membership = Membership.objects.get(user=game_master, club=club)
    receiver_char = Character.objects.create(club=club, owner=gm_membership, name="GM Char")
    trade = Trade.objects.create(
        club=club,
        sender=sender_char,
        receiver=receiver_char,
        status=Trade.Status.ACCEPTED,
        sender_approved=True,
        receiver_approved=False,
    )
    # Receiver (game_master) needs to approve
    assert _labels(rf, game_master, club) == {"Trades": 1}
    # Sender (player) already approved
    assert _labels(rf, player, club) == {}
    trade.delete()


def test_trade_other_statuses_not_counted(rf, club, player, game_master, character):
    # Trades in DECLINED, COMPLETED, CANCELLED should not be counted
    sender_char = character
    gm_membership = Membership.objects.get(user=game_master, club=club)
    receiver_char = Character.objects.create(club=club, owner=gm_membership, name="GM Char")
    for status in [Trade.Status.DECLINED, Trade.Status.COMPLETED, Trade.Status.CANCELLED]:
        trade = Trade.objects.create(
            club=club,
            sender=sender_char,
            receiver=receiver_char,
            status=status,
        )
        assert _labels(rf, player, club) == {}
        assert _labels(rf, game_master, club) == {}
        trade.delete()


def test_trade_cross_club_isolation(rf, club, other_club, player, game_master, character):
    # Trade in other_club should not affect club counts
    sender_char = character
    # Create a GM membership in other_club
    other_gm = Membership.objects.create(
        user=game_master, club=other_club, is_game_master=True
    )
    other_char = Character.objects.create(club=other_club, owner=other_gm, name="GM Char")
    trade = Trade.objects.create(
        club=other_club,
        sender=sender_char,
        receiver=other_char,
        status=Trade.Status.REQUESTED,
    )
    assert _labels(rf, player, club) == {}
    assert _labels(rf, game_master, club) == {}
    assert _labels(rf, game_master, other_club) == {"Trades": 1}
    trade.delete()
