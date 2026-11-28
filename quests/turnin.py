"""Shared turn-in card context for the quest page and the dashboard modal."""

from ledger.services import available_items


def turnin_context(quest, character):
    """Build ``turnin_rows`` and ``rewards`` for the turn-in card partial.

    Both ``quests.views.play.detail`` and
    ``accounts.views.dashboard_quests.dashboard_quest_turnin`` render
    ``quests/play/_turn_in_card.html``. This helper keeps the two context
    payloads identical so the dashboard modal shows the same Rewards list
    and unit names as the quest page.
    """
    have = available_items(character)
    rows = []
    for req in quest.requirements.select_related("item"):
        has = have.get(req.item_id, 0)
        rows.append(
            {
                "item": req.item,
                "needed": req.quantity,
                "has": has,
                "short": max(0, req.quantity - has),
                "unit_name": req.item.unit_name if req.item.is_stacked else "",
            }
        )
    return {
        "turnin_rows": rows,
        "rewards": quest.rewards.select_related("item"),
    }
