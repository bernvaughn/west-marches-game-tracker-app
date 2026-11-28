from accounts.models import Membership, User
from items.models import Item
from ledger import demo as ledger_demo
from ledger.models import LedgerEntry
from ledger.services import Line, record

from .life import archive, mark_dead
from .models import Character, ItemNote, JunkMark

CHARACTERS = [
    ("alice@example.com", "Aria Windrunner", 5),
    ("alice@example.com", "Wren Thistledown", 2),
    ("alice@example.com", "Pip Quickfoot", 1),
    ("bob@example.com", "Borin Stonefist", 4),
    ("bob@example.com", "Garrick Ashdown", 3),
    ("bob@example.com", "Tilda Brightwater", 1),
]
GEAR_NOTE = "Demo: starting gear"
GEAR = {
    "Aria Windrunner": {"Rope": 1, "Healing potion": 2, "Torch": 5},
    "Borin Stonefist": {"Longsword": 1, "Torch": 3},
    "Garrick Ashdown": {"Longsword": 1},
    "Tilda Brightwater": {"Priest's Pack": 1},
}
SPARE_PELT_NOTE = "Demo: a spare pelt"

# Stacked gear for Aria (U123-U131 demo)
STACKED_GEAR = {
    "Aria Windrunner": {"Parchment": 25, "Hempen cord": 40},
}
STACKED_GEAR_NOTE = "Demo: stacked supplies"

SHEETS = {
    "Aria Windrunner": {
        "char_class": "Ranger",
        "species": "Elf",
        "alignment": "Neutral Good",
        "pronouns": "she/her",
        "strength": 10,
        "dexterity": 18,
        "constitution": 12,
        "intelligence": 11,
        "wisdom": 16,
        "charisma": 9,
        "armor_class": 15,
        "max_hp": 38,
        "perception_bonus": 5,
        "xp": 6500,
        "description": "A wary scout who guards the road north.",
    },
    "Wren Thistledown": {
        "char_class": "Rogue",
        "species": "Halfling",
        "alignment": "Chaotic Neutral",
        "pronouns": "they/them",
        "dexterity": 17,
        "charisma": 14,
        "armor_class": 13,
        "max_hp": 22,
        "xp": 1000,
        "description": "Quick fingers and a quicker tongue.",
    },
    "Borin Stonefist": {
        "char_class": "Fighter",
        "species": "Dwarf",
        "alignment": "Lawful Good",
        "pronouns": "he/him",
        "strength": 17,
        "dexterity": 8,
        "constitution": 16,
        "intelligence": 10,
        "wisdom": 8,
        "charisma": 11,
        "armor_class": 18,
        "max_hp": 44,
        "perception_bonus": -1,
        "xp": 2700,
        "description": "A shield-bearer who never leaves a torch unlit.",
    },
    "Tilda Brightwater": {
        "char_class": "Cleric",
        "species": "Human",
        "alignment": "Lawful Good",
        "pronouns": "she/her",
        "strength": 10,
        "dexterity": 12,
        "constitution": 14,
        "intelligence": 11,
        "wisdom": 16,
        "charisma": 13,
        "armor_class": 16,
        "max_hp": 10,
        "perception_bonus": 5,
        "xp": 0,
        "description": "A devoted cleric who carries an unopened Priest's Pack.",
    },
    "Pip Quickfoot": {
        "char_class": "Rogue",
        "species": "Halfling",
        "alignment": "Chaotic Neutral",
        "pronouns": "they/them",
        "dexterity": 16,
        "charisma": 12,
        "armor_class": 14,
        "max_hp": 12,
        "perception_bonus": 3,
        "xp": 300,
        "description": "A halfling rogue with light fingers and a lighter heart.",
    },
    "Garrick Ashdown": {
        "char_class": "Fighter",
        "species": "Human",
        "alignment": "Neutral Good",
        "pronouns": "he/him",
        "strength": 16,
        "dexterity": 12,
        "constitution": 15,
        "intelligence": 10,
        "wisdom": 11,
        "charisma": 10,
        "armor_class": 16,
        "max_hp": 30,
        "perception_bonus": 1,
        "xp": 1800,
        "description": "A fallen shield-bearer, now memorialized.",
    },
}


def seed(club):
    for email, name, level in CHARACTERS:
        owner = Membership.objects.get(club=club, user__email=email)
        character, created = Character.objects.get_or_create(
            club=club, owner=owner, name=name, defaults={"level": level}
        )
        if character.level is None:
            character.level = level
            character.save(update_fields=["level"])
        # Fill sheet fields only while blank, so a user's later edit survives a re-run.
        changed = []
        for field, value in SHEETS.get(name, {}).items():
            if getattr(character, field) in (None, ""):
                setattr(character, field, value)
                changed.append(field)
        if changed:
            character.save(update_fields=changed)
    _give_gear(club)
    _give_stacked_gear(club)
    _give_borin_spare_pelt(club)
    _seed_item_note(club)
    _open_demo_stall(club)
    _seed_borin_capacity(club)
    _seed_dead_and_archived(club)


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


def _give_stacked_gear(club):
    """Give Aria stacked items (Parchment sheets, Hempen cord feet)."""
    ledger_demo.seed(club)
    gm = User.objects.get(email="gm@example.com")
    for name, gear in STACKED_GEAR.items():
        character = Character.objects.get(club=club, name=name)
        if LedgerEntry.objects.filter(character=character, note=STACKED_GEAR_NOTE).exists():
            continue
        found = {i.name: i for i in Item.objects.filter(club=club, name__in=gear)}
        lines = [Line(found[i], q) for i, q in gear.items() if i in found]
        if not lines:
            continue
        record(character, "award", lines, note=STACKED_GEAR_NOTE, actor=gm)


def _give_borin_spare_pelt(club):
    """Borin holds one Wolf pelt: partial progress (1 of 3) on 'Pelts for the Tanner'.

    Idempotent: the ledger note guard skips a re-run, and a missing item is skipped.
    """
    ledger_demo.seed(club)
    gm = User.objects.get(email="gm@example.com")
    borin = Character.objects.filter(club=club, name="Borin Stonefist").first()
    pelt = Item.objects.filter(club=club, name="Wolf pelt").first()
    if borin is None or pelt is None:
        return
    if LedgerEntry.objects.filter(character=borin, note=SPARE_PELT_NOTE).exists():
        return
    record(borin, "award", [Line(pelt, 1)], note=SPARE_PELT_NOTE, actor=gm)


def _seed_item_note(club):
    """Add an ItemNote for Aria's Rope (U122 demo)."""
    aria = Character.objects.filter(club=club, name="Aria Windrunner").first()
    rope = Item.objects.filter(club=club, name="Rope").first()
    if aria is None or rope is None:
        return
    ItemNote.objects.get_or_create(
        character=aria, item=rope, defaults={"text": "Good for climbing and tying up goblins."}
    )


def _open_demo_stall(club):
    """Borin sells two spare torches. Aria's switch stays off for the walk-through."""
    borin = Character.objects.filter(club=club, name="Borin Stonefist").first()
    torch = Item.objects.filter(club=club, name="Torch").first()
    if borin is None or torch is None:
        return
    _, created = JunkMark.objects.get_or_create(
        character=borin, item=torch, defaults={"quantity": 2}
    )
    if created:  # only on first create, so a user's later change survives a re-run
        borin.shop_open = True
        borin.save(update_fields=["shop_open"])

    # Also give Aria a junk mark for 5 sheets of Parchment (U123-U131 demo)
    aria = Character.objects.filter(club=club, name="Aria Windrunner").first()
    parchment = Item.objects.filter(club=club, name="Parchment").first()
    if aria is not None and parchment is not None:
        JunkMark.objects.get_or_create(character=aria, item=parchment, defaults={"quantity": 5})


def _seed_borin_capacity(club):
    """Borin gets a manual carrying capacity override of 300 lb (only while None)."""
    borin = Character.objects.filter(club=club, name="Borin Stonefist").first()
    if borin is not None and borin.carrying_capacity_lb is None:
        borin.carrying_capacity_lb = 300
        borin.save(update_fields=["carrying_capacity_lb"])


def _seed_dead_and_archived(club):
    """Garrick Ashdown (Bob) is dead; Pip Quickfoot (Alice) is archived.

    Guarded by the created flag / is_dead / is_archived so a re-run does not
    write duplicate status changes.
    """
    gm = Membership.objects.get(club=club, user__email="gm@example.com")

    # Garrick Ashdown: died 10 days ago
    garrick = Character.objects.filter(club=club, name="Garrick Ashdown").first()
    if garrick is not None and not garrick.is_dead:
        from datetime import timedelta

        from django.utils import timezone

        died_on = timezone.localdate() - timedelta(days=10)
        mark_dead(garrick, by=gm, died_on=died_on, note="Fell in the Goblin Caves.")

    # Pip Quickfoot: archived
    pip = Character.objects.filter(club=club, name="Pip Quickfoot").first()
    if pip is not None and not pip.is_archived:
        archive(pip, by=gm, note="Player moved away.")
