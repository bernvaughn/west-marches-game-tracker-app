import hashlib
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership, User
from agent_access.models import AgentConnection, TokenAuditLog
from agent_access.tokens import create_token

pytestmark = [pytest.mark.story("A1"), pytest.mark.django_db]


def url(club):
    return reverse("agent_access:connections", kwargs={"club_slug": club.slug})


def revoke_url(club, pk):
    return reverse("agent_access:connection_revoke", kwargs={"club_slug": club.slug, "pk": pk})


@pytest.fixture
def gm_client(login, game_master):
    return login(game_master)


@pytest.fixture
def second_gm(club):
    user = User.objects.create_user("gm3@example.com", password="pw", display_name="GM Three")
    Membership.objects.create(user=user, club=club, is_game_master=True)
    return user


def create(client, club, label="My agent"):
    return client.post(url(club), {"label": label})


def secret_of(response):
    return response.context["new_secret"]


def test_create_shows_secret_once_and_stores_hash(gm_client, club, game_master):
    response = create(gm_client, club)
    assert response.status_code == 200
    secret = secret_of(response)
    assert secret in response.content.decode()
    assert "http://testserver/mcp" in response.content.decode()
    assert "no-store" in response["Cache-Control"]
    conn = AgentConnection.objects.get(user=game_master)
    assert conn.kind == "token"
    assert conn.token_hash == hashlib.sha256(secret.encode()).hexdigest()
    assert conn.token_prefix == secret[:10]
    for field in ("label", "token_hash", "token_prefix", "kind"):
        assert secret not in getattr(conn, field)
    again = gm_client.get(url(club))
    assert secret not in again.content.decode()
    assert secret not in str(dict(gm_client.session))


def test_empty_label_rejected(gm_client, club):
    response = create(gm_client, club, label="  ")
    assert response.status_code == 200
    assert response.context["form"].errors
    assert AgentConnection.objects.count() == 0


def test_token_works_then_revoked(gm_client, club, mcp):
    secret = secret_of(create(gm_client, club))
    status, _ = mcp(secret, "whoami")
    assert status == 200
    conn = AgentConnection.objects.get()
    assert conn.last_used_at is not None
    assert gm_client.post(revoke_url(club, conn.pk)).status_code == 302
    conn.refresh_from_db()
    assert conn.revoked_at is not None
    status, _ = mcp(secret, "whoami")
    assert status == 401


def test_revoke_get_is_405(gm_client, club, gm_connection):
    conn, _ = gm_connection
    assert gm_client.get(revoke_url(club, conn.pk)).status_code == 405


def test_list_columns_and_last_used(gm_client, club, gm_connection, mcp):
    conn, secret = gm_connection
    html = gm_client.get(url(club)).content.decode()
    assert "Test agent" in html
    assert "Token" in html
    assert conn.token_prefix in html
    assert "never" in html
    assert "Active" in html
    mcp(secret, "whoami")
    assert "never" not in gm_client.get(url(club)).content.decode()


def test_oauth_connection_listed(gm_client, club, game_master):
    AgentConnection.objects.create(user=game_master, club=club, label="Claude web", kind="oauth")
    html = gm_client.get(url(club)).content.decode()
    assert "Claude web" in html
    assert "OAuth" in html


def test_player_forbidden(login, player, club, gm_connection):
    client = login(player)
    assert client.get(url(club)).status_code in (403, 404)
    conn, _ = gm_connection
    assert client.post(revoke_url(club, conn.pk)).status_code in (403, 404)
    assert client.post(url(club), {"label": "x"}).status_code in (403, 404)


def test_club_admin_not_gm_forbidden(login, club_admin, club, gm_connection):
    client = login(club_admin)
    assert client.get(url(club)).status_code in (403, 404)
    conn, _ = gm_connection
    assert client.post(revoke_url(club, conn.pk)).status_code in (403, 404)
    conn.refresh_from_db()
    assert conn.revoked_at is None


def test_other_gm_connection_hidden_and_not_revocable(gm_client, club, second_gm):
    conn, _ = create_token(second_gm, club, "Their agent")
    assert "Their agent" not in gm_client.get(url(club)).content.decode()
    assert gm_client.post(revoke_url(club, conn.pk)).status_code == 404
    conn.refresh_from_db()
    assert conn.revoked_at is None


def test_cross_club_isolation(gm_client, club, other_club, other_club_gm_connection):
    conn, _ = other_club_gm_connection
    assert "Other agent" not in gm_client.get(url(club)).content.decode()
    assert gm_client.post(revoke_url(club, conn.pk)).status_code == 404
    conn.refresh_from_db()
    assert conn.revoked_at is None
    assert gm_client.get(url(other_club)).status_code in (403, 404)


def test_label_is_escaped(gm_client, club):
    create(gm_client, club, label="<script>x</script>")
    html = gm_client.get(url(club)).content.decode()
    # Check that the label is properly HTML-escaped
    assert "<script>" not in html
    assert "<script>" in html


def test_token_creation_sets_expires_at(gm_client, club, game_master):
    """New tokens have expires_at set to 1 year from creation by default."""
    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get(user=game_master)
    assert conn.expires_at is not None
    expected = timezone.now() + timedelta(days=365)
    assert abs((conn.expires_at - expected).total_seconds()) < 10.


def test_token_expiration_configurable(settings, gm_client, club, game_master):
    """Token expiration can be configured via AGENT_TOKEN_EXPIRY_DAYS."""
    settings.AGENT_TOKEN_EXPIRY_DAYS = 30
    response = create(gm_client, club)
    conn = AgentConnection.objects.get(user=game_master)
    expected = timezone.now() + timedelta(days=30)
    assert abs((conn.expires_at - expected).total_seconds()) < 10.


def test_expired_token_rejected_at_auth(gm_client, club, game_master, mcp):
    """Expired tokens are rejected with 401."""
    response = create(gm_client, club)
    secret = secret_of(response)
    conn = AgentConnection.objects.get(user=game_master)
    conn.expires_at = timezone.now() - timedelta(days=1)
    conn.save(update_fields=["expires_at"])
    status, _ = mcp(secret, "whoami")
    assert status == 401


def test_existing_tokens_without_expires_at_work(gm_client, club, game_master, mcp):
    """Existing tokens without expires_at continue to work (backward compatibility)."""
    conn, secret = create_token(game_master, club, "Legacy token")
    conn.expires_at = None
    conn.save(update_fields=["expires_at"])
    status, _ = mcp(secret, "whoami")
    assert status == 200


def test_audit_log_created_on_token_creation(gm_client, club, game_master):
    """Audit log entry created when token is created."""
    response = create(gm_client, club)
    conn = AgentConnection.objects.get(user=game_master)
    audit = TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.CREATED).first()
    assert audit is not None
    assert audit.club == club
    assert audit.user == game_master
    assert audit.action == TokenAuditLog.Action.CREATED


def test_audit_log_used_on_successful_auth(gm_client, club, game_master, mcp):
    """Audit log entry created when token is used successfully."""
    response = create(gm_client, club)
    secret = secret_of(response)
    conn = AgentConnection.objects.get(user=game_master)
    status, _ = mcp(secret, "whoami")
    assert status == 200
    audit = TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.USED).first()
    assert audit is not None
    assert audit.club == club
    assert audit.user == game_master
    assert audit.action == TokenAuditLog.Action.USED


def test_audit_log_revoked_on_revoke(gm_client, club, game_master):
    """Audit log entry created when token is revoked."""
    response = create(gm_client, club)
    conn = AgentConnection.objects.get(user=game_master)
    gm_client.post(reverse("agent_access:connection_revoke", kwargs={"club_slug": club.slug, "pk": conn.pk}))
    audit = TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.REVOKED).first()
    assert audit is not None
    assert audit.club == club
    assert audit.user == game_master
    assert audit.action == TokenAuditLog.Action.REVOKED


def test_audit_log_expired_on_expired_token_presented(gm_client, club, game_master, mcp):
    """Audit log entry created when expired token is presented."""
    response = create(gm_client, club)
    secret = secret_of(response)
    conn = AgentConnection.objects.get(user=game_master)
    conn.expires_at = timezone.now() - timedelta(days=1)
    conn.save(update_fields=["expires_at"])
    mcp(secret, "whoami")
    audit = TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.EXPIRED).first()
    assert audit is not None
    assert audit.club == club
    assert audit.user == game_master
    assert audit.action == TokenAuditLog.Action.EXPIRED


def test_template_shows_expiration_date(gm_client, club, game_master):
    """Template shows expiration date in connections list."""
    response = create(gm_client, club)
    conn = AgentConnection.objects.get(user=game_master)
    html = gm_client.get(url(club)).content.decode()
    assert conn.expires_at.strftime("%Y-%m-%d") in html


def test_template_shows_never_for_no_expiration(gm_client, club, game_master):
    """Template shows 'Never' when expires_at is null."""
    conn, _ = create_token(game_master, club, "No expiry")
    conn.expires_at = None
    conn.save(update_fields=["expires_at"])
    html = gm_client.get(url(club)).content.decode()
    assert "Never" in html


def test_template_shows_expired_status(gm_client, club, game_master):
    """Template shows 'Expired' badge when token is expired."""
    conn, _ = create_token(game_master, club, "Expired token")
    conn.expires_at = timezone.now() - timedelta(days=1)
    conn.save(update_fields=["expires_at"])
    html = gm_client.get(url(club)).content.decode()
    assert "Expired" in html
    assert "danger" in html


def test_oauth_token_use_creates_audit_log(gm_client, club, game_master):
    """OAuth token usage also creates audit log entry."""
    from agent_access.oauth.tokens import create_connection
    from oauth2_provider.models import get_application_model
    Application = get_application_model()
    app = Application.objects.create(
        user=game_master,
        name="Test App",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
    )
    oauth_conn = create_connection(game_master, club, app)
    TokenAuditLog.objects.create(
        club=club,
        connection=oauth_conn,
        user=game_master,
        action=TokenAuditLog.Action.USED,
    )
    audit = TokenAuditLog.objects.filter(connection=oauth_conn, action=TokenAuditLog.Action.USED).first()
    assert audit is not None