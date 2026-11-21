import secrets
import string

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from .models import Membership, PasswordHistory, User, WhitelistEntry


def generate_temporary_password():
    return secrets.token_urlsafe(9)


def set_temporary_password(user):
    """Set a new random password and force a change. Signs the user out everywhere."""
    password = generate_temporary_password()
    user.set_password(password)
    user.must_change_password = True
    user.save()
    return password


def get_or_create_member(
    club, email, display_name="", *, is_club_admin=False, is_game_master=False
):
    """Return (membership, temporary_password_or_None)."""
    email = email.strip().lower()
    with transaction.atomic():
        temp = None
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            temp = generate_temporary_password()
            user = User.objects.create_user(
                email, password=temp, display_name=display_name, must_change_password=True
            )
        membership, _ = Membership.objects.get_or_create(
            user=user,
            club=club,
            defaults={"is_club_admin": is_club_admin, "is_game_master": is_game_master},
        )
        WhitelistEntry.objects.get_or_create(club=club, email=email)
    return membership, temp


class ComplexityValidator:
    """Validate password complexity requirements.

    Requires at least:
    - 1 uppercase letter
    - 1 lowercase letter
    - 1 digit
    - 1 special character
    """

    def __init__(self):
        self.special_chars = set(string.punctuation)

    def validate(self, password, user=None):
        errors = []
        if not any(c.isupper() for c in password):
            errors.append(_("Password must contain at least one uppercase letter."))
        if not any(c.islower() for c in password):
            errors.append(_("Password must contain at least one lowercase letter."))
        if not any(c.isdigit() for c in password):
            errors.append(_("Password must contain at least one number."))
        if not any(c in self.special_chars for c in password):
            errors.append(_("Password must contain at least one special character."))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Password must contain at least one uppercase letter, one lowercase letter,"
            " one number, and one special character."
        )


class PasswordHistoryValidator:
    """Validate that the new password hasn't been used in the last 5 passwords."""

    def __init__(self, history_count=5):
        self.history_count = history_count

    def validate(self, password, user=None):
        if user is None or user.pk is None:
            return
        recent = PasswordHistory.objects.filter(user=user).order_by("-created")[
            : self.history_count
        ]
        for entry in recent:
            if check_password(password, entry.password_hash):
                raise ValidationError(
                    _("This password has been used recently. Please choose a different password."),
                    code="password_reused",
                )

    def get_help_text(self):
        return _("Password cannot be any of your last 5 passwords.")


def save_password_history(user, password):
    """Save a password to the user's history, keeping only the last 5."""
    PasswordHistory.objects.create(user=user, password_hash=make_password(password))
    # Keep only the last 5 entries
    ids_to_keep = list(
        PasswordHistory.objects.filter(user=user)
        .order_by("-created")
        .values_list("pk", flat=True)[:5]
    )
    PasswordHistory.objects.filter(user=user).exclude(pk__in=ids_to_keep).delete()
