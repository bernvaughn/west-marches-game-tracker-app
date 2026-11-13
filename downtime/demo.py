from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from items.models import Item

from .models import DowntimeAction, DowntimeEntry, DowntimeEntryItem
from .services import award

STARTING_POINTS = {"Aria Windrunner": 2, "Borin Stonefist": 1}


def seed(club):
    from player_characters.models import Character

    gm = User.objects.get(email="gm@example.com")
    for name, points in STARTING_POINTS.items():
        character = Character.objects.get(club=club, name=name)
        if not character.downtime_point_entries.exists():
            award(character, points, "Starting downtime points", by=gm, club=club)
    seed_actions(club)


def seed_actions(club):
    action, _ = DowntimeAction.objects.get_or_create(
        club=club,
        name="Work at a bakery",
        defaults={
            "description": "Spend a day kneading dough and see what the baker pays you with.",
            "cost": 1,
            "start_date": timezone.localdate() - timedelta(days=7),
        },
    )
    if action.entries.exists():
        return
    rolling_pin, _ = Item.objects.get_or_create(
        club=club,
        name="Golden rolling pin",
        defaults={
            "description": "A heavy rolling pin cast in gold. The baker's pride.",
            "rarity": "rare",
            "value_cp": 5000,
        },
    )
    bread, _ = Item.objects.get_or_create(
        club=club, name="Loaf of bread", defaults={"description": "A fresh loaf.", "value_cp": 2}
    )
    roll, _ = Item.objects.get_or_create(
        club=club, name="Sweet roll", defaults={"description": "Sticky and warm.", "value_cp": 5}
    )
    # (label, weight, coins in cp, [(item, quantity)])
    table = [
        ("Burnt loaf, no pay", 3, 0, []),
        ("A day wage", 5, 50, []),
        ("Good tips", 3, 100, []),
        ("A loaf of bread", 4, 0, [(bread, 1)]),
        ("Two sweet rolls", 3, 0, [(roll, 2)]),
        ("Wage and a loaf", 3, 20, [(bread, 1)]),
        ("A big order", 2, 250, []),
        ("Tips and sweet rolls", 2, 30, [(roll, 3)]),
        ("The baker's thanks", 1, 500, [(bread, 2)]),
        ("The golden rolling pin", 1, 0, [(rolling_pin, 1)]),
    ]
    for order, (label, weight, coins, items) in enumerate(table):
        entry = DowntimeEntry.objects.create(
            action=action, label=label, weight=weight, coins=coins, order=order
        )
        for item, quantity in items:
            DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=quantity)
