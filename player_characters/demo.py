from accounts.models import Membership, User
from items.models import Item
from ledger import demo as ledger_demo
from ledger.models import LedgerEntry
from ledger.services import Line, record

from .models import Character, JunkMark, Trade, TradeLine

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


SHEETS = {
    "Aria Windrunner": {
        "char_class": "Ranger",
        "species": "Elf",
        "alignment": "Neutral good",
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
        "alignment": "Chaotic neutral",
        "pronouns": "they/them",
        "dexterity": 17,
        "charisma": 14,
        "armor_class": 13,
        "max_hp": 22,
        "xp": 300,
        "description": "Quick fingers and a quicker tongue.",
    },
    "Borin Stonefist": {
        "char_class": "Fighter",
        "species": "Dwarf",
        "alignment": "Lawful good",
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
        # Fill sheet fields only while blank, so a user's later edit survives a re-run.
        changed = []
        for field, value in SHEETS.get(name, {}).items():
            if getattr(character, field) in (None, ""):
                setattr(character, field, value)
                changed.append(field)
        if changed:
            character.save(update_fields=changed)
    _give_gear(club)
    _open_demo_stall(club)
    _open_demo_trade(club)


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


def _open_demo_trade(club):
    """An accepted trade where Bob changed his side, so both must approve again."""
    aria = Character.objects.filter(club=club, name="Aria Windrunner").first()
    borin = Character.objects.filter(club=club, name="Borin Stonefist").first()
    torch = Item.objects.filter(club=club, name="Torch").first()
    rope = Item.objects.filter(club=club, name="Rope").first()
    if aria is None or borin is None or torch is None or rope is None:
        return
    if Trade.objects.filter(sender=aria, receiver=borin).exists():
        return
    trade = Trade.objects.create(
        club=club,
        sender=aria,
        receiver=borin,
        status=Trade.Status.ACCEPTED,
        note="Rope for torches?",
        sides_changed_by="receiver",
    )
    TradeLine.objects.create(trade=trade, from_sender=True, item=rope, quantity=1)
    TradeLine.objects.create(trade=trade, from_sender=False, item=torch, quantity=2)
