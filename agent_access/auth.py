"""Bearer authentication for the MCP endpoint. OAuth can add an authenticator later."""

from django.utils import timezone

from accounts.permissions import is_game_master

from .models import AgentConnection
from .tokens import hash_secret


def token_authenticator(raw):
    return (
        AgentConnection.objects.filter(kind=AgentConnection.Kind.TOKEN, token_hash=hash_secret(raw))
        .select_related("user", "club")
        .first()
    )


AUTHENTICATORS = [token_authenticator]


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
            return None
        if not is_game_master(connection.user, connection.club):
            return None
        AgentConnection.objects.filter(pk=connection.pk).update(last_used_at=timezone.now())
        return connection
    return None
