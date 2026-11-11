import base64
import hashlib
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from django.test import Client
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_grant_model

from accounts.models import Membership
from agent_access.models import AgentConnection

pytestmark = pytest.mark.story("A1")

REDIRECT = "http://localhost:6274/oauth/callback"
VERIFIER = "v" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)


def register(auth_method="none", **extra):
    body = {
        "client_name": "Test <b>agent</b>",
        "redirect_uris": [REDIRECT],
        "token_endpoint_auth_method": auth_method,
        "grant_types": ["authorization_code", "refresh_token"],
        **extra,
    }
    return Client().post("/oauth/register/", json.dumps(body), content_type="application/json")


def authorize_params(client_id, **extra):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "scope": "mcp",
        "state": "xyz",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "resource": "http://testserver/mcp",
    }
    params.update(extra)
    return params


def approve(client, client_id, club, allow=True, **extra):
    params = authorize_params(client_id, **extra)
    url = "/oauth/authorize/?" + urlencode(params)
    page = client.get(url)
    assert page.status_code == 200
    data = {k: v for k, v in params.items()}
    if allow:
        data["allow"] = "true"
    if club is not None:
        data["club"] = club.pk
    return page, client.post(url, data)


def code_of(response):
    assert response.status_code == 302, response.content
    return parse_qs(urlparse(response["Location"]).query)


def exchange(client_id, code, verifier=VERIFIER):
    return Client().post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )


@pytest.fixture
def client_id():
    return register().json()["client_id"]


@pytest.fixture
def gm_client(game_master):
    c = Client()
    c.force_login(game_master)
    return c


def get_token(gm_client, client_id, club):
    _, response = approve(gm_client, client_id, club)
    token = exchange(client_id, code_of(response)["code"])
    assert token.status_code == 200, token.content
    return token.json()


def test_discovery_documents(db):
    meta = Client().get("/.well-known/oauth-authorization-server").json()
    assert meta["issuer"] == "http://testserver"
    assert meta["authorization_endpoint"] == "http://testserver/oauth/authorize/"
    assert meta["token_endpoint"] == "http://testserver/oauth/token/"
    assert meta["registration_endpoint"] == "http://testserver/oauth/register/"
    assert meta["code_challenge_methods_supported"] == ["S256"]
    prm = Client().get("/.well-known/oauth-protected-resource/mcp").json()
    assert prm["resource"] == "http://testserver/mcp"
    assert prm["authorization_servers"] == ["http://testserver"]
    assert "mcp" in prm["scopes_supported"]


def test_registers_public_client_only(db):
    response = register()
    assert response.status_code == 201
    body = response.json()
    assert body["client_id"] and "client_secret" not in body
    assert register("client_secret_basic").status_code == 400
    assert register(grant_types=["client_credentials"]).status_code == 400


def test_full_flow_reaches_mcp(gm_client, client_id, club, game_master, mcp):
    token = get_token(gm_client, client_id, club)
    status, result = mcp(token["access_token"], "whoami")
    assert status == 200
    assert result["structuredContent"]["club_slug"] == club.slug
    connection = AgentConnection.objects.get(kind="oauth")
    assert connection.user == game_master and connection.club == club
    assert connection.approved_at and connection.oauth_application_id


def test_consent_page_lists_only_gm_clubs(gm_client, client_id, club, other_club, game_master, db):
    from accounts.models import Club

    third = Club.objects.create(name="Player Only Club", slug="player-only")
    Membership.objects.create(user=game_master, club=third, is_game_master=False)
    page, response = approve(gm_client, client_id, other_club)
    content = page.content.decode()
    select = content[content.index("<select") : content.index("</select>")]
    assert club.name in select
    assert other_club.name not in select and third.name not in select
    assert "&lt;b&gt;agent&lt;/b&gt;" in content
    assert response.status_code == 200  # form re-rendered with an error
    assert not AgentConnection.objects.filter(kind="oauth").exists()
    assert not get_grant_model().objects.exists()
    _, response = approve(gm_client, client_id, third)
    assert response.status_code == 200
    assert not AgentConnection.objects.filter(kind="oauth").exists()


def test_deny_makes_no_connection(gm_client, client_id, club):
    _, response = approve(gm_client, client_id, club, allow=False)
    assert code_of(response)["error"] == ["access_denied"]
    assert not AgentConnection.objects.filter(kind="oauth").exists()


def test_approval_prompt_auto_still_shows_consent(gm_client, client_id):
    page = gm_client.get(
        "/oauth/authorize/?" + urlencode(authorize_params(client_id, approval_prompt="auto"))
    )
    assert page.status_code == 200


def test_revoked_connection_gets_401(gm_client, client_id, club, mcp):
    token = get_token(gm_client, client_id, club)["access_token"]
    AgentConnection.objects.filter(kind="oauth").update(revoked_at=timezone.now())
    assert mcp(token, "whoami")[0] == 401


def test_lost_gm_status_gets_401(gm_client, client_id, club, game_master, mcp):
    token = get_token(gm_client, client_id, club)["access_token"]
    Membership.objects.filter(user=game_master, club=club).update(is_game_master=False)
    assert mcp(token, "whoami")[0] == 401


def test_expired_token_gets_401(gm_client, client_id, club, mcp):
    token = get_token(gm_client, client_id, club)["access_token"]
    get_access_token_model().objects.update(expires=timezone.now() - timedelta(seconds=1))
    assert mcp(token, "whoami")[0] == 401


def test_registration_token_refused_on_mcp(db, mcp):
    registration = register().json()["registration_access_token"]
    assert mcp(registration, "whoami")[0] == 401


def test_reapproval_for_other_club_replaces_old_token(
    gm_client, client_id, club, other_club, game_master, mcp
):
    Membership.objects.create(user=game_master, club=other_club, is_game_master=True)
    old = get_token(gm_client, client_id, club)["access_token"]
    new = get_token(gm_client, client_id, other_club)["access_token"]
    assert mcp(old, "whoami")[0] == 401
    status, result = mcp(new, "whoami")
    assert status == 200 and result["structuredContent"]["club_slug"] == other_club.slug


def test_401_names_resource_metadata(db, mcp_raw):
    response = mcp_raw("nope", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response.status_code == 401
    assert (
        'resource_metadata="http://testserver/.well-known/oauth-protected-resource/mcp"'
        in response["WWW-Authenticate"]
    )
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_pkce_required_and_verified(gm_client, client_id, club):
    params = authorize_params(client_id)
    del params["code_challenge"], params["code_challenge_method"]
    response = gm_client.get("/oauth/authorize/?" + urlencode(params))
    assert response.status_code != 200
    _, approved = approve(gm_client, client_id, club)
    bad = exchange(client_id, code_of(approved)["code"], verifier="w" * 64)
    assert bad.status_code == 400
