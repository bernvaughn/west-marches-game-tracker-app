"""Personal agent tokens. Only a sha256 hash is stored; the secret is shown once."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import AgentConnection

PREFIX_LEN = 10


def hash_secret(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def create_token(user, club, label, secret=None):
    """Create a token connection. Returns (connection, secret)."""
    secret = secret or "wm_" + secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(days=settings.AGENT_TOKEN_EXPIRY_DAYS)
    connection = AgentConnection.objects.create(
        user=user,
        club=club,
        label=label,
        kind=AgentConnection.Kind.TOKEN,
        token_hash=hash_secret(secret),
        token_prefix=secret[:PREFIX_LEN],
        approved_at=timezone.now(),
        expires_at=expires_at,
    )
    return connection, secret
