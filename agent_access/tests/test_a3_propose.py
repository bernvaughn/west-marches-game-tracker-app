import json
from unittest import mock

import pytest
from django.utils import timezone

from accounts.models import Membership
from agent_access.mcp import tools_batches
from agent_access.models import ProposedBatch, ProposedItem
from agent_access.tokens import create_token
from items.models import Item
from ledger.models import LedgerEntry
from player_characters.models import Character

pytestmark = [pytest.mark.story("A3"), pytest.mark.django_db]


@pytest.fixture
def call(mcp_raw):
    def _call(secret, tool, **arguments):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        result = mcp_raw(secret, body, headers={"HTTP_HOST": "testserver"}).json()["result"]
        return result.get("isError", False), result

    return _call


@pytest.fixture
def world(club, other_club, character, item, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    other_owner = Membership.objects.create(
        user=other_player, club=other_club, is_game_master=False
    )
    return {
        "char": character,
        "char2": Character.objects.create(club=club, owner=owner, name="Bram"),
        "item": item,
        "retired": Item.objects.create(club=club, name="Old", retired=True),
        "pending": ProposedItem.objects.create(club=club, name="Gem"),
        "rejected": ProposedItem.objects.create(
            club=club, name="Bad", status=ProposedItem.Status.REJECTED
        ),
        "o_char": Character.objects.create(club=other_club, owner=other_owner, name="Zed"),
        "o_item": Item.objects.create(club=other_club, name="Other"),
        "o_pending": ProposedItem.objects.create(club=other_club, name="OG"),
    }


def coin(w, cp=100, **kw):
    return {"character_id": w["char"].pk, "coins_cp": cp, **kw}


def test_valid_batch(call, gm_connection, world, club):
    _, secret = gm_connection
    lines = [
        coin(world, 250, note="<script>x</script>"),
        {"character_id": world["char2"].pk, "item_id": world["item"].pk, "quantity": 3},
        {"character_id": world["char"].pk, "proposed_item_id": world["pending"].pk},
    ]
    err, res = call(secret, "propose_awards", idempotency_key="k1", lines=lines)
    assert not err
    data = res["structuredContent"]
    batch = ProposedBatch.objects.get()
    assert data["created"] is True and data["status"] == "pending"
    assert data["review_url"] == f"http://testserver/c/{club.slug}/agent/batches/{batch.pk}/"
    assert batch.date == timezone.localdate()
    assert batch.lines.count() == 3
    first, second, third = batch.lines.order_by("pk")
    assert first.coins == 250 and first.note == "<script>x</script>"
    assert second.quantity == 3 and third.quantity == 1
    assert LedgerEntry.objects.count() == 0


def test_same_key_returns_existing(call, gm_connection, world):
    _, secret = gm_connection
    _, a = call(secret, "propose_awards", idempotency_key="k", lines=[coin(world, 5)])
    _, b = call(secret, "propose_awards", idempotency_key="k", lines=[coin(world, 9)])
    assert a["structuredContent"]["created"] is True
    assert b["structuredContent"]["created"] is False
    assert a["structuredContent"]["batch_id"] == b["structuredContent"]["batch_id"]
    assert ProposedBatch.objects.count() == 1
    assert b["structuredContent"]["lines"][0]["coins_cp"] == 5


def test_same_key_other_connection(call, gm_connection, other_club_gm_connection, world, club):
    _, secret = gm_connection
    _, other = other_club_gm_connection
    call(secret, "propose_awards", idempotency_key="k", lines=[coin(world)])
    err, _ = call(
        other,
        "propose_awards",
        idempotency_key="k",
        lines=[{"character_id": world["o_char"].pk, "coins_cp": 1}],
    )
    assert not err
    _, second = create_token(gm_connection[0].user, club, "Second")
    err, _ = call(second, "propose_awards", idempotency_key="k", lines=[coin(world)])
    assert not err
    assert ProposedBatch.objects.count() == 3


def test_cross_club_rejected(call, gm_connection, other_club_gm_connection, world):
    _, secret = gm_connection
    bad = [
        {"character_id": world["o_char"].pk, "coins_cp": 1},
        {"character_id": world["char"].pk, "item_id": world["o_item"].pk},
        {"character_id": world["char"].pk, "proposed_item_id": world["o_pending"].pk},
    ]
    for n, line in enumerate(bad):
        err, res = call(secret, "propose_awards", idempotency_key=f"x{n}", lines=[line])
        assert err and "Line 1" in res["content"][0]["text"]
    assert ProposedBatch.objects.count() == 0
    _, other = other_club_gm_connection
    call(
        other,
        "propose_awards",
        idempotency_key="o",
        lines=[{"character_id": world["o_char"].pk, "coins_cp": 1}],
    )
    err, res = call(secret, "get_batch", batch_id=ProposedBatch.objects.get().pk)
    assert err and "not found" in res["content"][0]["text"]


def test_rejections(call, gm_connection, world):
    _, secret = gm_connection
    c, it = world["char"].pk, world["item"].pk
    cases = [
        [coin(world, -5)],
        [coin(world, 0)],
        [{"character_id": c, "item_id": it, "quantity": 0}],
        [{"character_id": c, "item_id": it, "coins_cp": 5}],
        [{"character_id": c}],
        [coin(world, 1, quantity=2)],
        [coin(world), {"character_id": c, "item_id": world["retired"].pk}],
        [{"character_id": c, "proposed_item_id": world["rejected"].pk}],
        [coin(world, 1, date="nope")],
        [coin(world)] * 201,
        [coin(world, 1, note="x" * 1001)],
        [],
    ]
    for n, lines in enumerate(cases):
        err, res = call(secret, "propose_awards", idempotency_key=f"r{n}", lines=lines)
        assert err, lines
    err, res = call(
        secret,
        "propose_awards",
        idempotency_key="d",
        lines=[coin(world)],
        date="2024-13-45",
    )
    assert err
    err, res = call(secret, "propose_awards", idempotency_key=" ", lines=[coin(world)])
    assert err
    err, res = call(secret, "propose_awards", idempotency_key="n", lines=[coin(world, -1)])
    assert "Line 1" in res["content"][0]["text"]
    assert ProposedBatch.objects.count() == 0


def test_race_returns_existing(gm_connection, world, club, game_master):
    connection, _ = gm_connection
    from agent_access.mcp.server import AgentContext

    ctx = AgentContext(connection=connection, user=game_master, club=club)
    lines = [tools_batches.AwardLine(character_id=world["char"].pk, coins_cp=3)]
    first = tools_batches.propose_awards(ctx, None, "race", lines)
    with mock.patch.object(
        tools_batches, "_existing", side_effect=[None, ProposedBatch.objects.get()]
    ):
        second = tools_batches.propose_awards(ctx, None, "race", lines)
    assert first["created"] and second["created"] is False
    assert second["batch_id"] == first["batch_id"]
    assert ProposedBatch.objects.count() == 1


def test_get_batch_status(call, gm_connection, world):
    _, secret = gm_connection
    call(secret, "propose_awards", idempotency_key="g", lines=[coin(world)])
    batch = ProposedBatch.objects.get()
    _, res = call(secret, "get_batch", batch_id=batch.pk)
    assert res["structuredContent"]["status"] == "pending"
    assert len(res["structuredContent"]["lines"]) == 1
    batch.status = ProposedBatch.Status.CONFIRMED
    batch.save()
    _, res = call(secret, "get_batch", batch_id=batch.pk)
    assert res["structuredContent"]["status"] == "confirmed"
    assert json.dumps(res)
