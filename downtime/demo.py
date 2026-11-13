from accounts.models import User

from .services import award

STARTING_POINTS = {"Aria Windrunner": 2, "Borin Stonefist": 1}


def seed(club):
    from player_characters.models import Character

    gm = User.objects.get(email="gm@example.com")
    for name, points in STARTING_POINTS.items():
        character = Character.objects.get(club=club, name=name)
        if not character.downtime_point_entries.exists():
            award(character, points, "Starting downtime points", by=gm, club=club)
