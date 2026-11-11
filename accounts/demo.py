from .models import Club, Membership, Message, User

DEMO_PASSWORD = "demo-password"
DEMO_LOGINS = [
    ("admin@example.com", "Site admin"),
    ("gm@example.com", "Club admin and game master"),
    ("alice@example.com", "Player"),
    ("bob@example.com", "Player"),
]


def _user(email, name, superuser=False):
    user = User.objects.filter(email=email).first()
    if user:
        return user
    make = User.objects.create_superuser if superuser else User.objects.create_user
    return make(email, password=DEMO_PASSWORD, display_name=name, must_change_password=False)


def seed():
    club, _ = Club.objects.get_or_create(slug="demo", defaults={"name": "Demo Marches"})
    _user("admin@example.com", "Site Admin", superuser=True)
    gm = _user("gm@example.com", "Gwen the GM")
    Membership.objects.get_or_create(
        user=gm, club=club, defaults={"is_club_admin": True, "is_game_master": True}
    )
    for email, name in (("alice@example.com", "Alice"), ("bob@example.com", "Bob")):
        Membership.objects.get_or_create(user=_user(email, name), club=club)
    alice = Membership.objects.get(user__email="alice@example.com", club=club)
    Message.objects.get_or_create(
        club=club,
        sender=alice,
        body="I think Gwen forgot the silver ring from the goblin cave.",
    )
    return club
