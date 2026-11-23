from django.contrib.auth.forms import AuthenticationForm


class CaseInsensitiveEmailAuthenticationForm(AuthenticationForm):
    """Authentication form that lower-cases the email (username) before lookup.

    Emails are stored lower-cased (UserManager.normalize_email, WhitelistForm,
    get_or_create_member). Django's default ModelBackend looks up USERNAME_FIELD
    (email) case-sensitively, so "Bob@Example.COM" fails to match a stored
    "bob@example.com". Lower-casing the input here makes login case-insensitive.
    """

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username:
            username = username.lower()
        return username
