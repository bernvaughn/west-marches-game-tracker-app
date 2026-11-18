import hashlib
from datetime import timedelta

import pytest
from django.conf import settings
from django.urls import reverse

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
    assert "&lt;script&gt;" in html
    assert "<script>x" not in html


# New tests for token expiration and audit logging


def test_token_expires_after_configured_days(gm_client, club, game_master):
    """Tokens should expire after AGENT_TOKEN_EXPIRY_DAYS."""
    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get(user=game_master)
    assert conn.expires_at is not None
    expected_expires = conn.created + timedelta(days=settings.AGENT_TOKEN_EXPIRY_DAYS)
    # Allow 1 minute tolerance for test execution time
    assert abs((conn.expires_at - expected_expires).total_seconds()) < 60


def test_default_expiry_is_one_year(gm_client, club, game_master):
    """Default expiry should be 1 year (365 days)."""
    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get(user=game_master)
    assert conn.expires_at is not None

    expected_diff = conn.expires_at - conn.created
    # Check total hours instead of days to avoid rounding issues
    assert expected_diff.total_seconds() / 3600 == pytest.approx(
        settings.AGENT_TOKEN_EXPIRY_DAYS * 24, rel=0.01
    )


def test_expired_token_rejected_at_authentication(gm_client, club, mcp, game_master):
    """Expired tokens should be rejected at authentication."""
    from django.utils import timezone

    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get(user=game_master)

    # Manually expire the token
    conn.expires_at = timezone.now() - timedelta(days=1)
    conn.save()

    # Token should be rejected
    secret = secret_of(response)
    status, _ = mcp(secret, "whoami")
    assert status == 401


def test_token_use_logs_audit_entry(gm_client, club, mcp):
    """Token use should create an audit log entry."""
    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get()

    # Before use, no USE audit log
    assert (
        TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.USE).count() == 0
    )

    # Use the token
    secret = secret_of(response)
    status, _ = mcp(secret, "whoami")
    assert status == 200

    # After use, there should be a USE audit log
    use_logs = TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.USE)
    assert use_logs.count() == 1
    assert use_logs.first().user == conn.user
    assert use_logs.first().club == conn.club


def test_token_create_logs_audit_entry(gm_client, club, game_master):
    """Token creation should create an audit log entry."""
    # Before create, no CREATE audit log
    assert TokenAuditLog.objects.filter(action=TokenAuditLog.Action.CREATE).count() == 0

    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get(user=game_master)

    # After create, there should be a CREATE audit log
    create_logs = TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.CREATE)
    assert create_logs.count() == 1
    assert create_logs.first().user == game_master
    assert create_logs.first().club == club


def test_token_revoke_logs_audit_entry(gm_client, club):
    """Token revocation should create an audit log entry."""
    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get()

    # Before revoke, no REVOKE audit log
    assert (
        TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.REVOKE).count()
        == 0
    )

    # Revoke the token
    assert gm_client.post(revoke_url(club, conn.pk)).status_code == 302

    # After revoke, there should be a REVOKE audit log
    revoke_logs = TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.REVOKE)
    assert revoke_logs.count() == 1
    assert revoke_logs.first().user == conn.user
    assert revoke_logs.first().club == conn.club


def test_expired_token_use_logs_expire_audit_entry(gm_client, club, mcp):
    """When an expired token is used, it should log an EXPIRE audit entry."""
    from django.utils import timezone

    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get()

    # Manually expire the token
    conn.expires_at = timezone.now() - timedelta(days=1)
    conn.save()

    # No EXPIRE audit log yet
    assert (
        TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.EXPIRE).count()
        == 0
    )

    # Try to use the expired token
    secret = secret_of(response)
    status, _ = mcp(secret, "whoami")
    assert status == 401

    # After use attempt, there should be an EXPIRE audit log
    expire_logs = TokenAuditLog.objects.filter(connection=conn, action=TokenAuditLog.Action.EXPIRE)
    assert expire_logs.count() == 1
    assert expire_logs.first().user == conn.user
    assert expire_logs.first().club == conn.club


def test_connection_list_shows_expires_at(gm_client, club, game_master):
    """The connection list should show the expires_at column."""
    response = create(gm_client, club)
    assert response.status_code == 200
    html = response.content.decode()
    assert "Expires" in html


def test_connection_list_shows_expired_badge(gm_client, club):
    """The connection list should show an Expired badge for expired tokens."""
    from django.utils import timezone

    response = create(gm_client, club)
    assert response.status_code == 200
    conn = AgentConnection.objects.get()

    # Manually expire the token
    conn.expires_at = timezone.now() - timedelta(days=1)
    conn.save()

    # Get the list page
    html = gm_client.get(url(club)).content.decode()

    # Should show Expired badge
    assert "Expired" in html or "expired" in html


def test_active_token_shows_active_badge(gm_client, club):
    """The connection list should show an Active badge for non-expired tokens."""
    create(gm_client, club)
    # Get the list page
    html = gm_client.get(url(club)).content.decode()

    # Should show Active badge
    assert "Active" in html
