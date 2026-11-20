"""Ledger service: the only place that writes ledger entries.

Also holds the stacked-item conversion service (stories U123, U124).
"""

from dataclasses import dataclass

from django.db import transaction
from django.db.models import F, Sum

from agent_access.models import ProposedBatch, ProposedLine
from downtime.models import DowntimeEntryItem
from ledger.models import LedgerEntry, LedgerLine
from ledger.services import Line, record_many
from player_characters.models import Character, JunkMark
from quests.models import QuestRequirement, QuestReward
from shops.models import ShopStock
from starting_equipment.models import (
    MagicItemStartingOption,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassLine,
    StartingEquipmentRequest,
)

from .models import ContainerSlotOption, Item
from .stacked import unit_label


def item_is_referenced(item):
    """True if any model points at the item (any relation, including CASCADE/SET_NULL ones)."""
    for rel in item._meta.related_objects:
        if rel.related_model._default_manager.filter(**{rel.field.name: item}).exists():
            return True
    return False


def delete_or_retire(item):
    """Delete an unused item; retire a used one. Returns True when deleted."""
    with transaction.atomic():
        if item_is_referenced(item):
            item.retired = True
            item.save(update_fields=["retired"])
            return False
        item.delete()
        return True


INT_LIMIT = 2147483647


class StackedConversionError(Exception):
    """Raised when a stacked-item conversion must be refused; it writes nothing."""


@dataclass(frozen=True)
class ConversionPreview:
    """Impact of converting ``item`` to stacked. Computed without writing anything."""

    item: Item
    holders: list
    total_owned: int
    shop_line_count: int
    junk_mark_count: int
    reference_count: int
    refusal_reasons: list
    non_blocking_warnings: list


def conversion_preview(item, factor=1):
    """Preview converting ``item`` to stacked. Writes nothing.

    ``factor`` is how many units one old item is worth; it defaults to 1 so
    the preview can run without a conversion factor (it then only flags totals
    already at the integer limit).
    """
    refusals = []
    if item.is_container:
        refusals.append(f'"{item.name}" is a container and cannot be stacked.')
    if item.is_stacked:
        refusals.append(f'"{item.name}" is already stacked.')

    holders = []
    total_owned = 0
    overflow = []
    non_positive = []
    rows = (
        LedgerLine.objects.filter(item=item)
        .values("entry__character_id")
        .annotate(total=Sum("quantity"))
        .order_by("entry__character_id")
    )
    char_ids = [row["entry__character_id"] for row in rows]
    characters = {c.pk: c for c in Character.objects.filter(pk__in=char_ids)}
    for row in rows:
        owned = row["total"] or 0
        character = characters.get(row["entry__character_id"])
        new_total = owned * factor
        holders.append(
            {"id": character.pk, "name": character.name, "owned": owned, "new": new_total}
        )
        total_owned += owned
        if new_total > INT_LIMIT:
            overflow.append(character.name)
        if owned <= 0:
            non_positive.append(character.name)
    if overflow:
        refusals.append(
            f"Converting by factor {factor} would push a quantity past the {INT_LIMIT} limit for: "
            + ", ".join(overflow)
            + "."
        )
    if non_positive:
        refusals.append(
            "These holders have a zero or negative net total and cannot be converted: "
            + ", ".join(non_positive)
            + "."
        )

    pending_proposal = ProposedLine.objects.filter(
        item=item, batch__status=ProposedBatch.Status.PENDING
    ).exists()
    if pending_proposal:
        refusals.append(
            f'A pending agent proposal names "{item.name}". '
            f"Confirm or discard it before converting."
        )

    shop_line_count = ShopStock.objects.filter(item=item).count()
    junk_mark_count = item.junk_marks.count()
    reference_count = (
        QuestRequirement.objects.filter(item=item).count()
        + QuestReward.objects.filter(item=item).count()
        + ContainerSlotOption.objects.filter(item=item).count()
        + StartingEquipmentClassLine.objects.filter(item=item).count()
        + StartingEquipmentBackgroundLine.objects.filter(item=item).count()
        + MagicItemStartingOption.objects.filter(item=item).count()
        + StartingEquipmentRequest.objects.filter(item=item).count()
        + DowntimeEntryItem.objects.filter(item=item).count()
    )

    warnings = []
    if reference_count:
        warnings.append(
            f"{reference_count} quest, container, starting-equipment or downtime rows reference "
            f'"{item.name}". Their quantities mean units for a stacked item and are not changed '
            f"by conversion."
        )

    return ConversionPreview(
        item=item,
        holders=holders,
        total_owned=total_owned,
        shop_line_count=shop_line_count,
        junk_mark_count=junk_mark_count,
        reference_count=reference_count,
        refusal_reasons=refusals,
        non_blocking_warnings=warnings,
    )


def convert_to_stacked(item, factor, unit_name, actor=None):
    """Convert ``item`` to stacked inside one atomic transaction.

    Multiplies every holder's owned quantity by ``factor`` once (one
    adjustment ledger entry per holder), turns the item's shop lines into
    bundle lines of ``factor`` units keeping their stock, and scales junk
    marks. Raises :class:`StackedConversionError` and writes nothing on any
    refusal.
    """
    if factor < 1:
        raise StackedConversionError("Factor must be at least 1.")
    unit_name = (unit_name or "").strip()
    if not unit_name:
        raise StackedConversionError("A stacked item needs a unit name.")
    if len(unit_name) > 40:
        raise StackedConversionError("Unit name must be at most 40 characters.")

    preview = conversion_preview(item, factor=factor)
    if preview.refusal_reasons:
        raise StackedConversionError(" ".join(preview.refusal_reasons))

    with transaction.atomic():
        item = Item.objects.select_for_update().get(pk=item.pk)
        # Re-run every refusal check inside the lock.
        preview = conversion_preview(item, factor=factor)
        if preview.refusal_reasons:
            raise StackedConversionError(" ".join(preview.refusal_reasons))

        item.is_stacked = True
        item.unit_name = unit_name
        item.value_units = factor
        item.save(update_fields=["is_stacked", "unit_name", "value_units"])

        if factor > 1:
            specs = []
            note = f"Converted to stacked item: each {item.name} is now {unit_label(item, factor)}"
            for holder in preview.holders:
                owned = holder["owned"]
                if owned <= 0:
                    continue
                character = Character.objects.get(pk=holder["id"])
                specs.append(
                    dict(
                        character=character,
                        kind=LedgerEntry.Kind.ADJUSTMENT,
                        lines=[Line(item=item, quantity=owned * (factor - 1))],
                        note=note,
                        actor=actor,
                    )
                )
            if specs:
                record_many(specs)

        ShopStock.objects.filter(item=item).update(bundle_units=factor)
        JunkMark.objects.filter(item=item).update(quantity=F("quantity") * factor)

    return preview


def can_toggle_stacked(item):
    """Whether the edit form or admin may flip is_stacked directly.

    An unsaved item may be created stacked. A saved item that is referenced
    anywhere (owned, listed in a shop, slotted in a container, required or
    rewarded by a quest, starting equipment, downtime) must go through
    conversion so owned counts are multiplied instead of silently
    reinterpreted. An unreferenced item has no counts to break.
    """
    if item.pk is None:
        return True
    return not item_is_referenced(item)
