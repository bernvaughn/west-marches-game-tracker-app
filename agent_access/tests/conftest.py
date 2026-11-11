import json

import pytest
from django.test import Client

from accounts.models import Membership, User
from agent_access.tokens import create_token

MCP_HEADERS = {
    "HTTP_ACCEPT": "application/json, text/event-stream",
    "HTTP_MCP_PROTOCOL_VERSION": "2025-11-25",
}


@pytest.fixture
def gm_connection(game_master, club):
    return create_token(game_master, club, "Test agent")


@pytest.fixture
def other_club_gm_connection(other_club):
    user = User.objects.create_user("gm2@example.com", password="pw", display_name="GM Two")
    Membership.objects.create(user=user, club=other_club, is_game_master=True)
    return create_token(user, other_club, "Other agent")


@pytest.fixture
def mcp_raw():
    def call(secret, body, headers=None):
        extra = dict(MCP_HEADERS)
        if secret is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {secret}"
        extra.update(headers or {})
        return Client().post(
            "/mcp", data=json.dumps(body), content_type="application/json", **extra
        )

    return call


@pytest.fixture
def mcp(mcp_raw):
    def call(secret, tool, **arguments):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        response = mcp_raw(secret, body)
        data = response.json()
        return response.status_code, data.get("result", data)

    return call
