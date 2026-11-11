from datetime import timedelta

from django.utils import timezone

from items.models import Item

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
