"""Personal agent tokens. Only a sha256 hash is stored; the secret is shown once."""

import hashlib
import secrets

from django.conf import settings
from django.utils import timezone

from .models import AgentConnection, TokenAuditLog

PREFIX_LEN = 10


def hash_secret(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def create_token(user, club, label, secret=None):
    """Create a token connection. Returns (connection, secret)."""
    secret = secret or "wm_" + secrets.token_urlsafe(32)
    now = timezone.now()
    expires_at = now + timezone.timedelta(days=settings.AGENT_TOKEN_EXPIRY_DAYS)

    connection = AgentConnection.objects.create(
        user=user,
        club=club,
        label=label,
        kind=AgentConnection.Kind.TOKEN,
        token_hash=hash_secret(secret),
        token_prefix=secret[:PREFIX_LEN],
        approved_at=now,
        expires_at=expires_at,
    )

    # Log the create action
    TokenAuditLog.objects.create(
        action=TokenAuditLog.Action.CREATE,
        connection=connection,
        user=user,
        club=club,
        metadata={"expires_at": expires_at.isoformat()},
    )

    return connection, secret
