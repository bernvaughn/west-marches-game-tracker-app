import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from agent_access.auth import authenticate_bearer
from agent_access.demo import DEMO_TOKEN
from agent_access.models import AgentConnection, ProposedBatch, ProposedItem

pytestmark = [pytest.mark.story("A1"), pytest.mark.django_db]


def rpc(method, params=None, id=1):
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def test_initialize(mcp_raw, gm_connection):
    _, secret = gm_connection
    body = rpc(
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    )
    response = mcp_raw(secret, body)
    assert response.status_code == 200
    assert response.json()["result"]["protocolVersion"] == "2025-11-25"


def test_tools_list_and_whoami(mcp_raw, mcp, gm_connection, club):
    _, secret = gm_connection
    names = [t["name"] for t in mcp_raw(secret, rpc("tools/list")).json()["result"]["tools"]]
    assert "whoami" in names
    status, result = mcp(secret, "whoami")
    assert status == 200
    assert result["structuredContent"]["club_slug"] == club.slug


def test_missing_and_wrong_token(mcp_raw, gm_connection):
    for secret in (None, "wm_wrong"):
        response = mcp_raw(secret, rpc("tools/list"))
        assert response.status_code == 401
        assert response["WWW-Authenticate"].startswith("Bearer")


def test_revoked_token(mcp_raw, gm_connection, mcp):
    connection, secret = gm_connection
    from django.utils import timezone

    connection.revoked_at = timezone.now()
    connection.save()
    response = mcp_raw(secret, rpc("tools/list"))
    assert response.status_code == 401
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_user_lost_game_master_flag(mcp_raw, gm_connection, club, game_master):
    _, secret = gm_connection
    from accounts.models import Membership

    Membership.objects.filter(user=game_master, club=club).update(is_game_master=False)
    response = mcp_raw(secret, rpc("tools/list"))
    assert response.status_code == 401
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_last_used_at_set(mcp, gm_connection):
    connection, secret = gm_connection
    assert connection.last_used_at is None
    mcp(secret, "whoami")
    connection.refresh_from_db()
    assert connection.last_used_at is not None


def test_other_club_token_sees_its_own_club(
    mcp, gm_connection, other_club_gm_connection, other_club
):
    _, secret = other_club_gm_connection
    _, result = mcp(secret, "whoami")
    assert result["structuredContent"]["club_slug"] == other_club.slug


def test_two_requests_in_a_row_and_methods(mcp, mcp_raw, gm_connection):
    _, secret = gm_connection
    assert mcp(secret, "whoami")[0] == 200
    assert mcp(secret, "whoami")[0] == 200
    client = Client()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {secret}"}
    assert client.get("/mcp", **headers).status_code == 405
    assert client.delete("/mcp", **headers).status_code == 405


def test_single_exchange_2026_07_28(mcp_raw, gm_connection, club):
    _, secret = gm_connection
    ns = "io.modelcontextprotocol/"
    body = rpc(
        "tools/call",
        {
            "name": "whoami",
            "arguments": {},
            "_meta": {
                ns + "protocolVersion": "2026-07-28",
                ns + "clientCapabilities": {},
                ns + "clientInfo": {"name": "test", "version": "1"},
            },
        },
    )
    response = mcp_raw(
        secret,
        body,
        headers={
            "HTTP_MCP_PROTOCOL_VERSION": "2026-07-28",
            "HTTP_MCP_METHOD": "tools/call",
            "HTTP_MCP_NAME": "whoami",
        },
    )
    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"]["club_slug"] == club.slug


def test_stub_urls_reverse_and_render(login, game_master, club, gm_connection):
    connection, _ = gm_connection
    batch = ProposedBatch.objects.create(
        club=club, connection=connection, user=game_master, date="2026-01-01", idempotency_key="k"
    )
    proposed = ProposedItem.objects.create(club=club, name="Thing")
    client = login(game_master)
    for name in ("connections", "batches", "proposed_items"):
        assert client.get(reverse(f"agent_access:{name}", args=[club.slug])).status_code == 200
    assert (
        client.get(reverse("agent_access:batch_detail", args=[club.slug, batch.pk])).status_code
        == 200
    )
    assert (
        client.get(
            reverse("agent_access:proposed_item_detail", args=[club.slug, proposed.pk])
        ).status_code
        == 200
    )
    for name, obj in (
        ("connection_revoke", connection),
        ("batch_confirm", batch),
        ("batch_discard", batch),
        ("batch_reverse", batch),
        ("proposed_item_approve", proposed),
        ("proposed_item_reject", proposed),
    ):
        assert reverse(f"agent_access:{name}", args=[club.slug, obj.pk])


def test_nav_links_for_gm_not_player(login, game_master, player, club):
    url = reverse("agent_access:index", args=[club.slug])
    gm_html = login(game_master).get(url).content.decode()
    player_html = login(player).get(url).content.decode()
    for name in ("connections", "batches", "proposed_items"):
        link = reverse(f"agent_access:{name}", args=[club.slug])
        assert link in gm_html
        assert link not in player_html


def test_seed_demo_agent_data_is_idempotent(db):
    call_command("seed_demo", stdout=open("/dev/null", "w"))
    call_command("seed_demo", stdout=open("/dev/null", "w"))
    assert AgentConnection.objects.filter(label="Demo agent").count() == 1
    batch = ProposedBatch.objects.get()
    assert batch.status == "pending"
    assert batch.lines.count() == 2
    assert ProposedItem.objects.filter(status="pending").count() == 1
    assert authenticate_bearer(f"Bearer {DEMO_TOKEN}") is not None
