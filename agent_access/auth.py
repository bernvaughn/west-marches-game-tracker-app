"""Bearer authentication for the MCP endpoint: personal tokens and OAuth access tokens."""

import logging

from django.utils import timezone

from accounts.permissions import is_game_master

from .models import AgentConnection
from .tokens import hash_secret

security_logger = logging.getLogger("security.mcp")


def token_authenticator(raw):
    return (
        AgentConnection.objects.filter(kind=AgentConnection.Kind.TOKEN, token_hash=hash_secret(raw))
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
    for authenticator in AUTHENTICATORS:
        connection = authenticator(raw)
        if connection is None:
            continue
        if connection.revoked_at is not None or not connection.user.is_active:
            security_logger.warning(
                "MCP authentication failed: token revoked or user inactive",
                extra={"user_id": connection.user_id if connection else None},
            )
            return None
        if not is_game_master(connection.user, connection.club):
            security_logger.warning(
                "MCP authentication failed: user not game master",
                extra={"user_id": connection.user_id, "club_id": connection.club_id},
            )
            return None
        AgentConnection.objects.filter(pk=connection.pk).update(last_used_at=timezone.now())
        security_logger.info(
            "MCP authentication successful",
            extra={
                "user_id": connection.user_id,
                "club_id": connection.club_id,
                "kind": connection.kind,
            },
        )
        return connection
    security_logger.warning("MCP authentication failed: invalid token")
    return None
