from accounts.models import Membership

from .models import Character

CHARACTERS = [("alice@example.com", "Aria Windrunner"), ("bob@example.com", "Borin Stonefist")]


def seed(club):
    for email, name in CHARACTERS:
        owner = Membership.objects.get(club=club, user__email=email)
        Character.objects.get_or_create(club=club, owner=owner, name=name)
