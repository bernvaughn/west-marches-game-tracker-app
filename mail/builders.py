"""Email building utilities: templates, context, extras registry."""

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from .models import ClubMailSettings

_extras_registry: dict[str, list] = {}


def register_email_extra(kind: str, fn):
    """Register an extra content function for a given email kind.

    fn(context) -> (text, html) where html is already mark_safe'd if needed.
    Multiple extras per kind are supported; they are concatenated.
    """
    _extras_registry.setdefault(kind, []).append(fn)


def render_extras(kind: str, context: dict) -> tuple[str, str]:
    """Render all extras for a kind, concatenating their output."""
    text_parts = []
    html_parts = []
    for fn in _extras_registry.get(kind, []):
        t, h = fn(context)
        text_parts.append(t)
        html_parts.append(h)
    return "\n".join(text_parts), "\n".join(html_parts)


def club_reply_to(club) -> str | None:
    """Get the club's contact email for reply-to, or None."""
    if club is None:
        return None
    try:
        return club.mail_settings.contact_email or None
    except ClubMailSettings.DoesNotExist:
        return None


def base_context(club, kind: str) -> dict:
    """Build the base context for email templates."""
    site_url = getattr(settings, "SITE_URL", None)
    if not site_url:
        allowed = getattr(settings, "ALLOWED_HOSTS", ["localhost"])
        site_url = f"https://{allowed[0]}" if allowed else "http://localhost"

    footer_lines = []
    if club:
        footer_lines.append(f"This email was sent by {club.name}.")
    else:
        footer_lines.append("This email was sent by Downtime Market.")

    contact_email = club_reply_to(club)
    if contact_email:
        footer_lines.append(f"Replies go to {contact_email}.")
    else:
        footer_lines.append("Replies to this email are not read.")

    return {
        "club": club,
        "site_url": site_url,
        "kind": kind,
        "footer_lines": footer_lines,
    }


def render_email(kind: str, template: str, context: dict, club) -> tuple[str, str, str]:
    """Render an email from a template plus extras.

    Returns (subject, text, html).
    The template is expected to be at mail/<template>.txt and mail/<template>.html.
    subject comes from context["subject"].
    """
    # Merge base context
    base = base_context(club, kind)
    base.update(context)

    # Render extras
    extra_text, extra_html = render_extras(kind, base)
    base["extra_text"] = extra_text
    base["extra_html"] = mark_safe(extra_html)

    # Render templates
    text = render_to_string(f"mail/{template}.txt", base).strip()
    html = render_to_string(f"mail/{template}.html", base).strip()

    subject = base.get("subject", "")
    return subject, text, html
