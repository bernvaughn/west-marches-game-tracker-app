from datetime import timedelta

import pytest

from accounts.models import Club
from mail.models import OneTimeToken
from mail.tokens import TTLS, consume, issue, peek, revoke_older


@pytest.fixture
def test_user(django_user_model):
    """Create a test user."""
    return django_user_model.objects.create_user("test@example.com", password="pw")


@pytest.fixture
def test_club(db):
    """Create a test club."""
    return Club.objects.create(name="Test Club", slug="test-club")


@pytest.mark.django_db
class TestTokens:
    def test_issue_returns_raw_token(self, test_user):
        """issue returns the raw token (only time it's available)."""
        raw = issue("welcome", test_user)
        assert isinstance(raw, str)
        assert len(raw) > 0

    def test_only_hash_stored(self, test_user):
        """Only the SHA-256 hash is stored, never the raw token."""
        raw = issue("welcome", test_user)
        token = OneTimeToken.objects.get(user=test_user, purpose="welcome")
        assert token.token_hash != raw
        # Verify it's the SHA-256 hash
        import hashlib

        expected = hashlib.sha256(raw.encode()).hexdigest()
        assert token.token_hash == expected

    def test_peek_returns_unused_unexpired(self, test_user):
        """peek returns the token if unused and unexpired."""
        raw = issue("welcome", test_user)
        token = peek(raw, "welcome")
        assert token is not None
        assert token.used_at is None
        assert token.purpose == "welcome"

    def test_peek_returns_none_for_wrong_purpose(self, test_user):
        """peek returns None if purpose doesn't match."""
        raw = issue("welcome", test_user)
        token = peek(raw, "password_reset")
        assert token is None

    def test_peek_returns_none_if_used(self, test_user):
        """peek returns None if token was already consumed."""
        raw = issue("welcome", test_user)
        consume(raw, "welcome")
        token = peek(raw, "welcome")
        assert token is None

    def test_peek_returns_none_if_expired(self, test_user):
        """peek returns None if token is expired."""
        raw = issue("welcome", test_user, ttl=timedelta(seconds=-1))
        token = peek(raw, "welcome")
        assert token is None

    def test_peek_never_consumes(self, test_user):
        """peek never sets used_at."""
        raw = issue("welcome", test_user)
        peek(raw, "welcome")
        peek(raw, "welcome")
        token = OneTimeToken.objects.get(user=test_user, purpose="welcome")
        assert token.used_at is None

    def test_consume_single_use(self, test_user):
        """consume works once, then returns None."""
        raw = issue("welcome", test_user)
        token1 = consume(raw, "welcome")
        assert token1 is not None
        assert token1.used_at is not None

        token2 = consume(raw, "welcome")
        assert token2 is None

    def test_consume_atomic_single_use(self, test_user):
        """consume uses conditional UPDATE for atomic single-use."""
        raw = issue("welcome", test_user)
        # Two concurrent consumes should only succeed once
        token1 = consume(raw, "welcome")
        token2 = consume(raw, "welcome")
        assert token1 is not None
        assert token2 is None
        # Only one token should exist and be used
        tokens = OneTimeToken.objects.filter(user=test_user, purpose="welcome")
        assert tokens.count() == 1
        assert tokens.first().used_at is not None

    def test_consume_wrong_purpose(self, test_user):
        """consume returns None if purpose doesn't match."""
        raw = issue("welcome", test_user)
        token = consume(raw, "password_reset")
        assert token is None
        # Original token should still be unused
        token = peek(raw, "welcome")
        assert token is not None

    def test_consume_expired(self, test_user):
        """consume returns None if token is expired."""
        raw = issue("welcome", test_user, ttl=timedelta(seconds=-1))
        token = consume(raw, "welcome")
        assert token is None

    def test_revoke_older(self, test_user, test_club):
        """revoke_older marks unused tokens as used."""
        raw1 = issue("welcome", test_user, club=test_club)
        raw2 = issue("welcome", test_user, club=test_club)
        raw3 = issue("password_reset", test_user, club=test_club)

        # Revoke welcome tokens for this user/club
        count = revoke_older("welcome", test_user, test_club)
        assert count == 2

        # Check they're revoked
        assert peek(raw1, "welcome") is None
        assert peek(raw2, "welcome") is None
        # Other purpose unaffected
        assert peek(raw3, "password_reset") is not None

    def test_revoke_older_club_none(self, test_user):
        """revoke_older with club=None matches club__isnull=True."""
        raw1 = issue("welcome", test_user, club=None)
        raw2 = issue("welcome", test_user, club=Club.objects.create(name="Test", slug="test"))

        count = revoke_older("welcome", test_user, club=None)
        assert count == 1
        assert peek(raw1, "welcome") is None
        assert peek(raw2, "welcome") is not None

    def test_revoke_older_only_unused(self, test_user, test_club):
        """revoke_older only affects unused, unexpired tokens."""
        raw1 = issue("welcome", test_user, club=test_club)
        issue("welcome", test_user, club=test_club)
        consume(raw1, "welcome")  # Use one

        count = revoke_older("welcome", test_user, test_club)
        assert count == 1  # Only the unused one

    def test_ttl_defaults(self):
        """TTLS dict has expected defaults."""
        assert "welcome" in TTLS
        assert "password_reset" in TTLS
        assert "rsvp" in TTLS
        assert "unsubscribe" in TTLS
        assert "email_change" in TTLS
        assert TTLS["welcome"] == timedelta(days=7)
        assert TTLS["password_reset"] == timedelta(hours=1)
        assert TTLS["unsubscribe"] == timedelta(days=365)
        assert TTLS["email_change"] == timedelta(hours=24)
        assert TTLS["rsvp"] is None

    def test_issue_requires_ttl_for_rsvp(self, test_user):
        """RSVP requires explicit TTL (no default)."""
        with pytest.raises(ValueError):
            issue("rsvp", test_user)  # No default TTL

        # Should work with explicit TTL
        raw = issue("rsvp", test_user, ttl=timedelta(hours=2))
        assert raw is not None

    def test_extra_stored(self, test_user):
        """extra JSON is stored with the token."""
        issue("welcome", test_user, extra={"session_id": 42})
        token = OneTimeToken.objects.get(user=test_user, purpose="welcome")
        assert token.extra == {"session_id": 42}
