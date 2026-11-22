import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import OneTimeToken

# Default TTLs for each purpose
TTLS = {
    "welcome": timedelta(days=7),
    "password_reset": timedelta(hours=1),
    "rsvp": None,  # caller sets TTL (until session starts)
    "unsubscribe": timedelta(days=365),
    "email_change": timedelta(hours=24),
}


def _hash_token(raw: str) -> str:
    """Return SHA-256 hex digest of the raw token."""
    return hashlib.sha256(raw.encode()).hexdigest()


def issue(
    purpose: str,
    user,
    club=None,
    ttl=None,
    extra=None,
) -> str:
    """Issue a new one-time token. Returns the raw token (only time it's available)."""
    if ttl is None:
        ttl = TTLS.get(purpose)
    if ttl is None:
        raise ValueError(f"No default TTL for purpose {purpose}; provide ttl")

    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires_at = timezone.now() + ttl

    OneTimeToken.objects.create(
        purpose=purpose,
        user=user,
        club=club,
        token_hash=token_hash,
        expires_at=expires_at,
        extra=extra or {},
    )
    return raw


def peek(raw: str, purpose: str) -> OneTimeToken | None:
    """Return the token if it exists, is unused, and unexpired. Does not consume."""
    token_hash = _hash_token(raw)
    now = timezone.now()
    return OneTimeToken.objects.filter(
        token_hash=token_hash,
        purpose=purpose,
        used_at__isnull=True,
        expires_at__gt=now,
    ).first()


def consume(raw: str, purpose: str) -> OneTimeToken | None:
    """Atomically consume a token (single use). Returns the token if consumed, else None."""
    token_hash = _hash_token(raw)
    now = timezone.now()

    with transaction.atomic():
        updated = OneTimeToken.objects.filter(
            token_hash=token_hash,
            purpose=purpose,
            used_at__isnull=True,
            expires_at__gt=now,
        ).update(used_at=now)

        if updated == 1:
            return OneTimeToken.objects.get(token_hash=token_hash, purpose=purpose)
    return None


def revoke_older(purpose: str, user, club=None) -> int:
    """Mark all unused tokens for the given purpose/user/club as used (revoked).

    club=None matches tokens with club__isnull=True.
    Returns the number of tokens revoked.
    """
    now = timezone.now()
    qs = OneTimeToken.objects.filter(
        purpose=purpose,
        user=user,
        used_at__isnull=True,
        expires_at__gt=now,
    )
    if club is None:
        qs = qs.filter(club__isnull=True)
    else:
        qs = qs.filter(club=club)

    return qs.update(used_at=now)
