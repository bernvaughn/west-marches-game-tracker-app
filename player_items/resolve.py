"""Resolve player-written items: promote a name_key group into a catalogue item.

All writes happen inside a single transaction so a failure rolls back the
catalogue item, ledger entries, resolved marks, history rows and notices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import Line, record_many
from player_items.models import PlayerItem, PlayerItemChange, PlayerNotice, normalize_name_key


class ResolveError(Exception):
    """Raised when a resolve cannot complete; the caller surfaces the message."""


@dataclass(frozen=True)
class Target:
    """Specification of the promotion target.

    For a new catalogue item, ``item`` is ``None`` and the remaining fields
    describe the Item to create. For an existing item, ``item`` is set.
    """

    item: Item | None = None
    name: str = ""
    is_stacked: bool = False
    unit_name: str = ""
    quantity_factor: int = 1


def _trigrams(text: str) -> set[str]:
    """Return the set of character trigrams of padded, normalized text."""
    padded = f"  {text}  "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def _similarity(a: str, b: str) -> float:
    """Trigon-style similarity between two normalized names (0.0 to 1.0)."""
    ta = _trigrams(a)
    tb = _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def suggest_matches(club, name: str) -> list[str]:
    """Return existing Item names in the club resembling ``name``.

    Pure-Python trigram-style similarity over normalized names. Suggests,
    never chooses.
    """
    normalized = normalize_name_key(name)
    names = list(Item.objects.for_club(club).values_list("name", flat=True))
    scored = [
        (similarity, existing)
        for existing in names
        if normalize_name_key(existing) != normalized
        and (similarity := _similarity(normalized, normalize_name_key(existing))) > 0
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [existing for _, existing in scored[:5]]


def _validate_entries(club, entries) -> None:
    if not entries:
        msg = "No open entries to promote."
        raise ResolveError(msg)
    for entry in entries:
        if entry.review != PlayerItem.Review.OPEN:
            msg = f"{entry.name!r} is no longer open."
            raise ResolveError(msg)
        if entry.club_id != club.id:
            msg = f"{entry.name!r} is not in this club."
            raise ResolveError(msg)


def _resolve_target(club, target: Target) -> Item:
    if target.item is not None:
        if target.item.club_id != club.id:
            msg = "That item belongs to a different club."
            raise ResolveError(msg)
        return target.item
    if Item.objects.for_club(club).filter(name=target.name).exists():
        matches = suggest_matches(club, target.name)
        msg = f'An item named "{target.name}" already exists in this club.'
        if matches:
            msg += f" Did you mean: {', '.join(matches)}?"
        raise ResolveError(msg)
    return Item.objects.create(
        club=club,
        name=target.name,
        is_stacked=target.is_stacked,
        unit_name=target.unit_name if target.is_stacked else "",
        value_cp=0,
        value_units=1,
    )


def _group_by_character(entries):
    """Group entries by character, preserving first-seen order."""
    groups = {}
    order = []
    for entry in entries:
        if entry.character_id not in groups:
            groups[entry.character_id] = []
            order.append(entry.character_id)
        groups[entry.character_id].append(entry)
    return [groups[character_id] for character_id in order]


def _notice_text(old_names, new_name, character_name) -> str:
    old = ", ".join(f'"{n}"' for n in old_names)
    if len(old_names) == 1:
        return f'Item {old} for {character_name} promoted to "{new_name}".'
    return f'Items {old} for {character_name} promoted to "{new_name}".'


def resolve(club, entries, target: Target, by):
    """Promote open player-written entries into a catalogue Item.

    One adjustment ledger entry per holder (coins unchanged), one
    PlayerItemChange row per entry keeping the old name, entries marked
    resolved, and one PlayerNotice per holder. All in one transaction.
    """
    entries = list(entries)
    with transaction.atomic():
        _validate_entries(club, entries)
        item = _resolve_target(club, target)
        for character_entries in _group_by_character(entries):
            character = character_entries[0].character
            total_quantity = sum(entry.quantity for entry in character_entries)
            line_quantity = total_quantity * target.quantity_factor
            record_many(
                [
                    dict(
                        character=character,
                        kind=LedgerEntry.Kind.ADJUSTMENT,
                        lines=[Line(item=item, quantity=line_quantity, coins=0)],
                        note="player-written item promoted",
                        date=date.today(),
                        actor=by,
                    )
                ]
            )
            old_names = []
            for entry in character_entries:
                change = PlayerItemChange.objects.create(
                    club=club,
                    character=character,
                    kind=PlayerItemChange.Kind.PROMOTED,
                    old_name=entry.name,
                    new_name=item.name,
                    quantity=entry.quantity,
                    item=item,
                    by=by,
                    note=f'Promoted player-written item "{entry.name}" to "{item.name}".',
                )
                entry.review = PlayerItem.Review.RESOLVED
                entry.resolved_by_change = change
                entry.save(update_fields=["review", "resolved_by_change"])
                old_names.append(entry.name)
            PlayerNotice.objects.create(
                membership=character.owner,
                club=club,
                character=character,
                kind=PlayerNotice.Kind.ITEM_PROMOTED,
                text=_notice_text(old_names, item.name, character.name),
            )
    return item
