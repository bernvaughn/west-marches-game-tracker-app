"""Builder for RSVP email extra (E6).

This module provides the build_rsvp_extra function that is registered
as an email extra for the 'reminder' kind.

The one-click token now carries the member (not a character). Each
reminder email contains one set of three buttons (Yes / Maybe / No)
for the member it is addressed to.
"""

from datetime import timedelta

from django.utils import timezone

from mail.tokens import issue


def build_rsvp_extra(context: dict) -> tuple[str, str]:
    """Build RSVP links for the session reminder email.

    Context contains: user, club, session, membership.
    Generates one token per answer; each token's extra carries
    session_id, member_id, and the answer.
    """
    membership = context.get("membership")
    club = context.get("club")
    session = context.get("session")

    if not all([membership, club, session]):
        return "", ""

    user = membership.user
    member_name = membership.user.display_name or membership.user.email

    text_parts = []
    html_parts = []

    for answer in ("yes", "maybe", "no"):
        token = issue(
            purpose="rsvp",
            user=user,
            club=club,
            ttl=_ttl_until_session_start(session),
            extra={"session_id": session.pk, "member_id": membership.pk, "answer": answer},
        )

        site_url = context.get("site_url", "")
        base_url = f"{site_url}/mail/rsvp/"
        url = f"{base_url}{token}/"

        label = answer.capitalize()

        # Text version
        text_parts.append(f"\n{member_name}:")
        text_parts.append(f"  {label}: {url}")

        # HTML version
        card_style = "margin: 16px 0; padding: 16px; border: 1px solid #e1e4e8; border-radius: 6px;"
        button_styles = {
            "yes": "background: #28a745;",
            "maybe": "background: #ffc107; color: #24292e;",
            "no": "background: #cb2431;",
        }
        html_parts.append(f'<div style="{card_style}">')
        html_parts.append(f'<strong style="font-size: 16px;">{member_name}</strong>')
        flex_style = "margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;"
        html_parts.append(f'<div style="{flex_style}">')
        html_parts.append(
            f'<a href="{url}" class="button" style="{button_styles[answer]}">{label}</a>'
        )
        html_parts.append("</div></div>")

    return "\n".join(text_parts), "\n".join(html_parts)


def _ttl_until_session_start(session) -> timedelta:
    """Calculate TTL until session starts."""
    now = timezone.now()
    if session.starts_at <= now:
        # Session already started, minimum TTL
        return timedelta(minutes=1)
    return session.starts_at - now
