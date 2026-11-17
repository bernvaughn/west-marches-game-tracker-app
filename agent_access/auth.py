"""Bearer authentication for the MCP endpoint: personal tokens and OAuth access tokens."""

from django.db import models
from django.utils import timezone

from accounts.permissions import is_game_master

from .models import AgentConnection, TokenAuditLog
from .tokens import hash_secret


def token_authenticator(raw):
    return (
        AgentConnection.objects.filter(
            kind=AgentConnection.Kind.TOKEN,
            token_hash=hash_secret(raw),
        )
        .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now()))
        .select_related("user", "club")
        .first()
    )


def oauth_authenticator(raw):
    """Map a valid OAuth access token to its connection. The caller checks revocation."""
    from .oauth.tokens import connection_for_access_token

    return connection_for_access_token(raw)


AUTHENTICATORS = [token_authenticator, oauth_authenticator]


def authenticate_bearer(header):
    """Return the live AgentConnection for an Authorization header, or None."""
    if not header:
        return None
    scheme, _, raw = header.partition(" ")
    raw = raw.strip()
    if scheme.lower() != "bearer" or not raw:
        return None

    # Check token auth first, including expired tokens for audit logging
    token_conn = (
        AgentConnection.objects.filter(
            kind=AgentConnection.Kind.TOKEN, token_hash=hash_secret(raw)
        )
        .select_related("user", "club")
        .first()
    )
    if token_conn is not None:
        if token_conn.is_expired:
            TokenAuditLog.objects.create(
                club=token_conn.club,
                connection=token_conn,
                user=token_conn.user,
                action=TokenAuditLog.Action.EXPIRED,
            )
            return None
        if token_conn.revoked_at is not None or not token_conn.user.is_active:
            return None
        if not is_game_master(token_conn.user, token_conn.club):
            return None
        AgentConnection.objects.filter(pk=token_conn.pk).update(last_used_at=timezone.now())
        TokenAuditLog.objects.create(
            club=token_conn.club,
            connection=token_conn,
            user=token_conn.user,
            action=TokenAuditLog.Action.USED,
        )
        return token_conn

    # OAuth authentication
    oauth_conn = oauth_authenticator(raw)
    if oauth_conn is not None:
        if oauth_conn.revoked_at is not None or not oauth_conn.user.is_active:
            return None
        if not is_game_master(oauth_conn.user, oauth_conn.club):
            return None
        AgentConnection.objects.filter(pk=oauth_conn.pk).update(last_used_at=timezone.now())
        TokenAuditLog.objects.create(
            club=oauth_conn.club,
            connection=oauth_conn,
            user=oauth_conn.user,
            action=TokenAuditLog.Action.USED,
        )
        return oauth_conn

    return None
