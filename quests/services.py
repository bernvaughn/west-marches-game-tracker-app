from django.db import transaction
from django.utils import timezone

from ledger.services import Line, available_items, record_many

from .models import QuestCompletion


class QuestError(Exception):
    pass


class QuestNotLive(QuestError):
    pass


class QuestLimitReached(QuestError):
    pass


class QuestNotAllowed(QuestError):
    pass


def completions_left(quest):
    if quest.max_completions is None:
        return None
    return max(0, quest.max_completions - quest.completions.count())


def character_completions_left(quest, character):
    if quest.max_per_character is None:
        return None
    used = quest.completions.filter(character=character).count()
    return max(0, quest.max_per_character - used)


def missing_items(quest, character):
    """Return [(item, n_missing)] for requirements the character cannot meet now."""
    have = available_items(character)
    missing = []
    for req in quest.requirements.select_related("item"):
        short = req.quantity - have.get(req.item_id, 0)
        if short > 0:
            missing.append((req.item, short))
    return missing


def turn_in(quest, character, actor, today=None):
    today = today or timezone.localdate()
    with transaction.atomic():
        if quest.club_id != character.club_id:
            raise QuestNotAllowed("This character belongs to a different club.")
        reqs = list(quest.requirements.select_related("item"))
        if not reqs:
            raise QuestNotAllowed("This quest has no requirements.")
        if not quest.is_live_on(today):
            raise QuestNotLive("This quest is not live.")
        if completions_left(quest) == 0:
            raise QuestLimitReached("This quest is full.")
        if character_completions_left(quest, character) == 0:
            raise QuestLimitReached(
                f"{character} has completed this quest the maximum number of times."
            )

        specs = [
            dict(
                character=character,
                kind="quest_turn_in",
                lines=[Line(item=r.item, quantity=-r.quantity) for r in reqs],
                note=f"Turned in for quest {quest.name}",
                date=today,
                actor=actor,
            )
        ]
        reward_lines = []
        coins = 0
        for rw in quest.rewards.select_related("item"):
            if rw.item_id and rw.quantity > 0:
                reward_lines.append(Line(item=rw.item, quantity=rw.quantity))
            coins += rw.coins
        if coins > 0:
            reward_lines.append(Line(coins=coins))
        if reward_lines:
            specs.append(
                dict(
                    character=character,
                    kind="quest_reward",
                    lines=reward_lines,
                    note=f"Reward for quest {quest.name}",
                    date=today,
                    actor=actor,
                )
            )
        record_many(specs)
        return QuestCompletion.objects.create(quest=quest, character=character, date=today)
