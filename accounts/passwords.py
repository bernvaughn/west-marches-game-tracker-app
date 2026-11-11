import secrets

from django.db import transaction

from .models import Membership, User, WhitelistEntry


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
