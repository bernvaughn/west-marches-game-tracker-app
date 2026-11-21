"""Template tags for the "needed for a quest" shop hint.

``{% quest_needs character as needs %}`` returns ``{item_id: [quest names]}``:
live quests in the character's club that are not full and not already finished
by this character, and that have a requirement for the item.
"""

from django import template
from django.db.models import Count
from django.utils import timezone

from quests.models import Quest, QuestCompletion

register = template.Library()


@register.simple_tag
def quest_needs(character):
    """Return {item_id: [quest names]} of quests that still need each item.

    Empty dict when `character` is None. Names are unique and ordered by quest
    name. Scoped to the character's club, so another club's quests never show.
    """
    if character is None:
        return {}
    today = timezone.localdate()
    counts = {
        row["quest"]: row["cnt"]
        for row in QuestCompletion.objects.filter(character=character)
        .values("quest")
        .annotate(cnt=Count("quest"))
    }
    needs: dict[int, list[str]] = {}
    for quest in (
        Quest.objects.for_club(character.club)
        .live_on(today)
        .annotate(done=Count("completions"))
        .prefetch_related("requirements")
        .order_by("name", "pk")
    ):
        if quest.max_completions is not None and quest.done >= quest.max_completions:
            continue
        if (
            quest.max_per_character is not None
            and counts.get(quest.pk, 0) >= quest.max_per_character
        ):
            continue
        for req in quest.requirements.all():
            names = needs.setdefault(req.item_id, [])
            if quest.name not in names:
                names.append(quest.name)
    return needs


@register.filter
def needed_for(needs, item_id):
    """Return the quest names that need `item_id`, per ``quest_needs``."""
    return needs.get(item_id, [])
