"""Email preference utilities (E8/M9).

Provides wants(), unsubscribe_link(), and unsubscribe_extra() for managing
per-membership email preferences and one-click unsubscribe.
"""

from django.conf import settings

from mail.models import EmailPreference
from mail.tokens import issue


def wants(membership, kind: str) -> bool:
    """Return whether the membership wants emails of the given kind.

    Args:
        membership: The Membership object.
        kind: The email kind ("reminder", "notice", "digest").

    Returns:
        True if enabled, False otherwise.
        With no row: reminder/notice default to True, digest defaults to False.
    """
    try:
        pref = EmailPreference.objects.get(membership=membership, kind=kind)
        return pref.enabled
    except EmailPreference.DoesNotExist:
        # Default: on for reminders and notices, off for digest (opt-in)
        return kind != "digest"


def unsubscribe_link(user, club, kind: str) -> str:
    """Generate an absolute unsubscribe URL for the given user/club/kind.

    Issues a OneTimeToken with purpose="unsubscribe", TTL 1 year,
    extra={"kind": pref_kind, "membership_id": membership.id} where
    pref_kind is the EmailPreference.Kind value ("reminder", "notice", "digest").
    Returns the absolute public URL /mail/unsubscribe/<token>/.
    """
    from accounts.models import Membership

    # Find the membership for this user and club
    membership = Membership.objects.get(user=user, club=club)

    # Map email kind to EmailPreference.Kind
    # "cancel" and "change" both map to "notice" preference
    pref_kind_map = {
        "reminder": "reminder",
        "cancel": "notice",
        "change": "notice",
        "digest": "digest",
    }
    pref_kind = pref_kind_map.get(kind, kind)

    # Issue a one-year unsubscribe token with kind and membership_id in extra
    raw_token = issue(
        purpose="unsubscribe",
        user=user,
        club=club,
        extra={"kind": pref_kind, "membership_id": membership.id},
    )

    # Build absolute URL from SITE_URL
    site_url = getattr(settings, "SITE_URL", None)
    if not site_url:
        allowed = getattr(settings, "ALLOWED_HOSTS", ["localhost"])
        site_url = f"https://{allowed[0]}" if allowed else "http://localhost"

    return f"{site_url}/mail/unsubscribe/{raw_token}/"


def unsubscribe_extra(kind: str):
    """Factory returning an extras function for the unsubscribe footer.

    The returned function appends an unsubscribe line (text and HTML)
    for the given kind. It resolves the membership from context via
    "membership", "user" + "club", or "game_master" (which is a membership).
    """
    # Map email kind to EmailPreference.Kind for checking wants()
    pref_kind_map = {
        "reminder": "reminder",
        "cancel": "notice",
        "change": "notice",
        "digest": "digest",
    }
    pref_kind = pref_kind_map.get(kind, kind)

    # Kind display names (use email kind for display)
    kind_names = {
        "reminder": "session reminders",
        "notice": "session notices",
        "cancel": "session cancellation notices",
        "change": "session change notices",
        "digest": "GM digests",
    }
    display = kind_names.get(kind, kind)

    def _extra_fn(context: dict) -> tuple[str, str]:
        # Try to get membership from context
        membership = context.get("membership")
        if membership is None:
            user = context.get("user")
            club = context.get("club")
            if user and club:
                from accounts.models import Membership

                try:
                    membership = Membership.objects.get(user=user, club=club)
                except Membership.DoesNotExist:
                    pass
        if membership is None:
            # Check for game_master (which is a Membership)
            membership = context.get("game_master")

        if membership is None:
            return "", ""

        # Check if this membership wants this kind of email
        if not wants(membership, pref_kind):
            return "", ""

        # Build unsubscribe link
        user = membership.user
        club = membership.club
        link = unsubscribe_link(user, club, kind)

        text = f"\n\nTo stop receiving {display}, visit: {link}"
        html = (
            f'\n\n<div class="extra">'
            f"To stop receiving <strong>{display}</strong>, "
            f'<a href="{link}">unsubscribe here</a>.'
            f"</div>"
        )
        return text, html

    return _extra_fn
