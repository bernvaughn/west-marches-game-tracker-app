"""Resolve player-written items: promote, merge, or match into catalogue items.

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
from player_items.models import PlayerItem, PlayerItemChange, PlayerNotice
from player_items.suggest import suggest_matches


class ResolveError(Exception):
    """Raised when a resolve cannot complete; the caller surfaces the message."""


@dataclass(frozen=True)
class Target:
    """Specification of the resolution target.

    For a new catalogue item (promote/merge), ``item`` is ``None`` and the
    remaining fields describe the Item to create. For an existing item
    (promote/match), ``item`` is set.
    """

    item: Item | None = None
    name: str = ""
    is_stacked: bool = False
    unit_name: str = ""
    quantity_factor: int = 1


def _validate_entries(club, entries) -> None:
    if not entries:
        msg = "No open entries to resolve."
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


def _notice_text(old_names, new_name, character_name, kind: str) -> str:
    old = ", ".join(f'"{n}"' for n in old_names)
    if len(old_names) == 1:
        return f'Item {old} for {character_name} {kind} to "{new_name}".'
    return f'Items {old} for {character_name} {kind} to "{new_name}".'


def resolve(club, entries, target: Target, by, *, mode: str = "promote"):
    """Resolve open player-written entries into a catalogue Item.

    Parameters
    ----------
    club : Club
        The club context.
    entries : iterable of PlayerItem
        Open player-written entries to resolve. Can span multiple name_keys.
    target : Target
        Target specification: new item fields or existing item.
    by : User
        The admin performing the action.
    mode : {"promote", "merge", "match"}
        - "promote": single name_key group -> new or existing item (original behavior)
        - "merge": multiple name_key groups -> new item
        - "match": multiple name_key groups -> existing item

    Returns
    -------
    Item
        The catalogue item the entries were resolved into.

    All operations are atomic: one ledger entry per holder (coins unchanged),
    one PlayerItemChange row per entry keeping the old name, entries marked
    resolved, and one PlayerNotice per holder.
    """
    entries = list(entries)
    with transaction.atomic():
        _validate_entries(club, entries)
        item = _resolve_target(club, target)

        change_kind = {
            "promote": PlayerItemChange.Kind.PROMOTED,
            "merge": PlayerItemChange.Kind.MERGED,
            "match": PlayerItemChange.Kind.MATCHED,
        }[mode]

        notice_kind = {
            "promote": PlayerNotice.Kind.ITEM_PROMOTED,
            "merge": PlayerNotice.Kind.ITEM_MERGED,
            "match": PlayerNotice.Kind.ITEM_MATCHED,
        }[mode]

        notice_verb = {
            "promote": "promoted",
            "merge": "merged",
            "match": "matched",
        }[mode]

        for character_entries in _group_by_character(entries):
            character = character_entries[0].character
            total_quantity = sum(entry.quantity for entry in character_entries)
            line_quantity = total_quantity * target.quantity_factor

            # One adjustment ledger entry per holder.
            # If matching to an existing item the holder already has, this
            # adjustment naturally adds to their existing quantity.
            record_many(
                [
                    dict(
                        character=character,
                        kind=LedgerEntry.Kind.ADJUSTMENT,
                        lines=[Line(item=item, quantity=line_quantity, coins=0)],
                        note=f"player-written item {notice_verb}",
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
                    kind=change_kind,
                    old_name=entry.name,
                    new_name=item.name,
                    quantity=entry.quantity,
                    item=item,
                    by=by,
                    note=(
                        f'{notice_verb.capitalize()} player-written item "{entry.name}" '
                        f'to "{item.name}".'
                    ),
                )
                entry.review = PlayerItem.Review.RESOLVED
                entry.resolved_by_change = change
                entry.save(update_fields=["review", "resolved_by_change"])
                old_names.append(entry.name)

            PlayerNotice.objects.create(
                membership=character.owner,
                club=club,
                character=character,
                kind=notice_kind,
                text=_notice_text(old_names, item.name, character.name, notice_verb),
            )
    return item
