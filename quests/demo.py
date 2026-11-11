from datetime import timedelta

from django.utils import timezone

from items.models import Item
from ledger import demo as ledger_demo
from ledger.models import LedgerEntry
from ledger.services import Line, record

from .models import Quest, QuestRequirement, QuestReward


def seed(club):
    quest, _ = Quest.objects.get_or_create(
        club=club,
        name="Pelts for the Tanner",
        defaults={
            "description": "The tanner pays well for wolf pelts.",
            "start_date": timezone.localdate() - timedelta(days=7),
        },
    )
    pelt = Item.objects.get(club=club, name="Wolf pelt")
    potion = Item.objects.get(club=club, name="Healing potion")
    QuestRequirement.objects.get_or_create(quest=quest, item=pelt, defaults={"quantity": 3})
    QuestReward.objects.get_or_create(quest=quest, item=None, coins=1000, defaults={"quantity": 0})
    QuestReward.objects.get_or_create(quest=quest, item=potion, defaults={"quantity": 1})

    _give_demo_pelts(club, pelt)


def _give_demo_pelts(club, pelt):
    from accounts.models import User
    from player_characters.models import Character

    ledger_demo.seed(club)  # starting coins first; it only runs for empty ledgers
    aria = Character.objects.get(club=club, name="Aria Windrunner")
    note = "Demo: pelts for the tanner"
    if not LedgerEntry.objects.filter(character=aria, note=note).exists():
        gm = User.objects.get(email="gm@example.com")
        record(aria, "award", [Line(pelt, 3)], note=note, actor=gm)
