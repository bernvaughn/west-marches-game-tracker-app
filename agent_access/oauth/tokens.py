import hashlib

from django.utils import timezone
from oauth2_provider.models import get_access_token_model

from agent_access.models import AgentConnection

SCOPE = "mcp"


def connection_for_access_token(raw):
    """Return the newest OAuth connection a valid `mcp` access token belongs to, or None."""
    checksum = hashlib.sha256(raw.encode()).hexdigest()
    token = (
        get_access_token_model()
        .objects.select_related("user", "application")
        .filter(token_checksum=checksum)
        .first()
    )
    # Registration access tokens have no user and a different scope: refused here.
    if token is None or token.user_id is None or not token.is_valid([SCOPE]):
        return None
    return (
        AgentConnection.objects.filter(
            kind=AgentConnection.Kind.OAUTH,
            user_id=token.user_id,
            oauth_application_id=token.application_id,
            approved_at__lte=token.created,
        )
        .select_related("user", "club")
        .order_by("-approved_at", "-pk")
        .first()
    )


def prepare_approval(user, application):
    """Revoke earlier connections for this user and client and drop their tokens."""
    AgentConnection.objects.filter(
        kind=AgentConnection.Kind.OAUTH,
        user=user,
        oauth_application=application,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())
    clear_grants(user, application)


def create_connection(user, club, application):
    return AgentConnection.objects.create(
        kind=AgentConnection.Kind.OAUTH,
        user=user,
        club=club,
        oauth_application=application,
        label=(application.name or "OAuth client")[:200],
        approved_at=timezone.now(),
    )


def clear_grants(user, application):
    from oauth2_provider.models import get_grant_model, get_refresh_token_model

    get_refresh_token_model().objects.filter(user=user, application=application).delete()
    get_access_token_model().objects.filter(user=user, application=application).delete()
    get_grant_model().objects.filter(user=user, application=application).delete()
