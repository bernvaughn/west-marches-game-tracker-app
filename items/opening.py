"""Opening a container: roll, ledger entry and opening record (slice B).

One atomic transaction: lock the character, check availability, roll,
write one ``opened`` ledger entry and create one ``ContainerOpening``.
"""

from __future__ import annotations

from django.db import transaction

from ledger.services import LedgerError, Line, available_items, record
from player_characters.models import Character

from .containers import roll_container
from .models import ContainerOpening


class OpenError(Exception):
    """Raised when a container cannot be opened."""


def open_container(character, container, actor, rng=None) -> ContainerOpening:
    """Open ``container`` for ``character`` by ``actor``.

    The whole open is a single atomic transaction: the character is locked,
    availability is re-checked inside the transaction, the container is
    rolled, one ``opened`` ledger entry is written (container -1, one +qty
    line per rolled item) and one ``ContainerOpening`` stores the result.
    """

    if not container.is_container:
        raise OpenError(f"{container} is not a container.")
    if container.club_id != character.club_id:
        raise OpenError(f"{container} is not in {character.club.name}'s club.")

    with transaction.atomic():
        # Lock the character so concurrent opens serialise
        # (same idiom as downtime/services.py; SQLite IMMEDIATE serialises writers).

        list(Character.objects.select_for_update().filter(pk=character.pk))

        if not container.slots.exists():
            raise OpenError(f"{container} has no slots and cannot be opened.")

        if available_items(character).get(container.pk, 0) < 1:
            raise OpenError(f"{character} has no {container} available to open.")

        roll = roll_container(container, rng)

        lines = [Line(item=container, quantity=-1)]
        lines.extend(Line(item=item, quantity=qty) for item, qty in roll.lines.items())

        try:
            entry = record(
                character,
                "opened",
                lines,
                note=f"Opened {container.name}",
                actor=actor,
            )
        except LedgerError as exc:
            raise OpenError(str(exc)) from exc

        return ContainerOpening.objects.create(
            entry=entry,
            container=container,
            character=character,
            result=roll.as_result(),
        )


def opening_view_model(opening):
    """Display rows for an opening's stored result.

    Hit items only, merged per item, in slot order, built from the entry's
    positive ledger lines (real item names after the open, never from the
    slot configuration).
    """

    merged = {}
    for line in opening.entry.lines.filter(quantity__gt=0).select_related("item").order_by("id"):
        row = merged.setdefault(line.item_id, {"item": line.item, "qty": 0})
        row["qty"] += line.quantity
    return list(merged.values())
