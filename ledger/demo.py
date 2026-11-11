from accounts.models import User

from .services import Line, record

STARTING_COINS = {"Aria Windrunner": 5000, "Borin Stonefist": 2000}


def seed(club):
    from player_characters.models import Character

    gm = User.objects.get(email="gm@example.com")
    for name, coins in STARTING_COINS.items():
        character = Character.objects.get(club=club, name=name)
        if not character.ledger_entries.exists():
            record(character, "award", [Line(coins=coins)], note="Starting coins", actor=gm)
