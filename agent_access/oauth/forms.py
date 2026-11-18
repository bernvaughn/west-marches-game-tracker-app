from urllib.parse import urlparse

from django import forms
from oauth2_provider.forms import AllowForm
from oauth2_provider.settings import oauth2_settings

from accounts.models import Club, Membership


def game_master_clubs(user):
    if user.is_superuser:
        return Club.objects.all().order_by("name")
    return Club.objects.filter(
        pk__in=Membership.objects.filter(user=user, is_game_master=True).values("club_id")
    ).order_by("name")


def validate_redirect_uris(redirect_uris):
    """
    Validate redirect URIs against OAuth2 provider settings.

    Returns a list of error messages (empty if valid).
    """
    errors = []

    if not redirect_uris:
        errors.append("At least one redirect URI is required.")
        return errors

    allowed_schemes = oauth2_settings.ALLOWED_REDIRECT_URI_SCHEMES
    allow_localhost = oauth2_settings.ALLOW_LOCALHOST_LOOPBACK

    for uri in redirect_uris:
        parsed = urlparse(uri)

        # Check scheme
        if parsed.scheme not in allowed_schemes:
            errors.append(
                f"Redirect URI '{uri}' uses scheme '{parsed.scheme}' which is not allowed. "
                f"Allowed schemes: {', '.join(allowed_schemes)}."
            )
            continue

        # Check localhost/loopback
        hostname = parsed.hostname
        is_loopback = hostname in ("127.0.0.1", "::1")
        is_localhost = hostname == "localhost"

        if is_localhost and not allow_localhost:
            errors.append(
                f"Redirect URI '{uri}' uses localhost which is only allowed in development mode."
            )
            continue

        # For loopback IPs, require http scheme (per RFC 8252)
        if is_loopback and parsed.scheme != "http":
            errors.append(f"Loopback redirect URI '{uri}' must use http scheme per RFC 8252.")
            continue

        # Check for fragments (not allowed per RFC 6749)
        if "#" in uri:
            errors.append(
                f"Redirect URI '{uri}' contains a fragment which is not allowed per RFC 6749."
            )
            continue

        # Check for userinfo credentials
        if "@" in parsed.netloc:
            errors.append(
                f"Redirect URI '{uri}' contains userinfo credentials which are not allowed."
            )
            continue

    return errors


class ConsentForm(AllowForm):
    club = forms.ModelChoiceField(queryset=Club.objects.none(), required=False, empty_label=None)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["club"].queryset = game_master_clubs(user)

    def clean(self):
        data = super().clean()
        if data.get("allow") and not data.get("club") and "club" not in self.errors:
            self.add_error("club", "Pick a club you are a game master of.")
        return data
