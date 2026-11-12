from accounts.models import Membership, User
from items.models import Item
from ledger import demo as ledger_demo
from ledger.models import LedgerEntry
from ledger.services import Line, record

from .models import Character

CHARACTERS = [
    ("alice@example.com", "Aria Windrunner", 5),
    ("alice@example.com", "Wren Thistledown", 2),
    ("bob@example.com", "Borin Stonefist", 4),
]
GEAR_NOTE = "Demo: starting gear"
GEAR = {
    "Aria Windrunner": {"Rope": 1, "Healing potion": 2, "Torch": 5},
    "Borin Stonefist": {"Longsword": 1, "Torch": 3},
}


def seed(club):
    for email, name, level in CHARACTERS:
        owner = Membership.objects.get(club=club, user__email=email)
        character, _ = Character.objects.get_or_create(
            club=club, owner=owner, name=name, defaults={"level": level}
        )
        if character.level is None:
            character.level = level
            character.save(update_fields=["level"])
    _give_gear(club)


def _give_gear(club):
    ledger_demo.seed(club)  # starting coins first; it only runs for empty ledgers
    gm = User.objects.get(email="gm@example.com")
    for name, gear in GEAR.items():
        character = Character.objects.get(club=club, name=name)
        if LedgerEntry.objects.filter(character=character, note=GEAR_NOTE).exists():
            continue
        found = {i.name: i for i in Item.objects.filter(club=club, name__in=gear)}
        lines = [Line(found[i], q) for i, q in gear.items() if i in found]
        if not lines:  # items are seeded separately; skip if they are not there yet
            continue
        record(character, "award", lines, note=GEAR_NOTE, actor=gm)
