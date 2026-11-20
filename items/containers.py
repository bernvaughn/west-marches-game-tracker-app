"""Container loot rolling, previews and configuration validation.

The roll is pure: it only reads the container's slots and options and never
writes to the database. All public dataclasses are frozen.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from .models import ContainerSlotOption, Item

MAX_DEPTH = 3


@dataclass(frozen=True)
class SlotOutcome:
    """Outcome of rolling a single slot."""

    slot_id: int
    position: int
    hit: bool
    option_id: int | None
    item_id: int | None
    qty: int


@dataclass(frozen=True)
class Roll:
    """Result of rolling every slot of a container, in slot order."""

    slots: list[SlotOutcome]
    lines: dict[Item, int]

    def as_result(self) -> list[dict]:
        """JSON-safe per-slot outcome list, in slot order."""

        return [
            {
                "slot_id": o.slot_id,
                "position": o.position,
                "hit": o.hit,
                "option_id": o.option_id,
                "item_id": o.item_id,
                "qty": o.qty if o.hit else 0,
            }
            for o in self.slots
        ]


@dataclass(frozen=True)
class PreviewOption:
    """One option inside a "pick one" preview row."""

    item: Item
    label: str
    qty_min: int
    qty_max: int
    weight_pct: int


@dataclass(frozen=True)
class PreviewRow:
    """One preview row per slot, in slot order."""

    item: Item | None
    label: str
    qty_min: int | None
    qty_max: int | None
    chance_pct: int
    options: tuple[PreviewOption, ...]
    unknown: bool
    masked: bool


def roll_container(container, rng=None) -> Roll:
    """Roll every slot of ``container`` and return a :class:`Roll`.

    Defaults to :class:`secrets.SystemRandom`. Draws from ``rng`` only when
    needed (chance below 100, several options, quantity range), so a scripted
    rng stays predictable. Issues no write queries and performs no saves.
    """

    if rng is None:
        rng = secrets.SystemRandom()

    slots = list(container.slots.prefetch_related("options__item").order_by("position", "id"))

    outcomes: list[SlotOutcome] = []
    lines: dict[Item, int] = {}

    for slot in slots:
        options = list(slot.options.all())

        # 1. Chance check. 100 always hits without drawing.
        if slot.chance_pct < 100:
            passes = rng.randint(1, 100) <= slot.chance_pct
        else:
            passes = True

        hit = False
        option_id = None
        item_id = None
        qty = 0
        option = None

        # 2. Pick one option, then 3. quantity.
        if passes and options:
            if len(options) == 1:
                option = options[0]
            else:
                total_weight = sum(o.weight for o in options)
                draw = rng.randrange(total_weight)
                running = 0
                option = options[-1]
                for candidate in options:
                    running += candidate.weight
                    if draw < running:
                        option = candidate
                        break

            option_id = option.pk
            item_id = option.item.pk
            if option.qty_min == option.qty_max:
                qty = option.qty_min
            else:
                qty = rng.randint(option.qty_min, option.qty_max)
            hit = True

        outcomes.append(
            SlotOutcome(
                slot_id=slot.pk,
                position=slot.position,
                hit=hit,
                option_id=option_id,
                item_id=item_id,
                qty=qty,
            )
        )

        if hit and item_id is not None:
            lines[option.item] = lines.get(option.item, 0) + qty

    return Roll(slots=outcomes, lines=lines)


def loot_preview(container, viewer_can_see_unknown) -> list[PreviewRow]:
    """Preview one row per slot, in slot order.

    Unknown slots are masked (``???``) unless the viewer can see them. Masked
    rows keep ``chance_pct`` and ``unknown=True`` but reveal no item, id or
    quantity.

    If ``container`` has a ``prefetched_slots`` attribute (set by a Prefetch),
    those slots are used instead of querying, avoiding N+1.
    """

    rows: list[PreviewRow] = []
    if hasattr(container, "prefetched_slots"):
        slots = container.prefetched_slots
    else:
        slots = list(container.slots.prefetch_related("options__item").order_by("position", "id"))

    for slot in slots:
        options = list(slot.options.all())
        masked = slot.unknown and not viewer_can_see_unknown

        if masked:
            rows.append(
                PreviewRow(
                    item=None,
                    label="???",
                    qty_min=None,
                    qty_max=None,
                    chance_pct=slot.chance_pct,
                    options=(),
                    unknown=True,
                    masked=True,
                )
            )
            continue

        if len(options) == 1:
            option = options[0]
            rows.append(
                PreviewRow(
                    item=option.item,
                    label=option.item.name,
                    qty_min=option.qty_min,
                    qty_max=option.qty_max,
                    chance_pct=slot.chance_pct,
                    options=(),
                    unknown=slot.unknown,
                    masked=False,
                )
            )
            continue

        total_weight = sum(o.weight for o in options)
        preview_options = tuple(
            PreviewOption(
                item=opt.item,
                label=opt.item.name,
                qty_min=opt.qty_min,
                qty_max=opt.qty_max,
                weight_pct=int(round(opt.weight * 100 / total_weight)),
            )
            for opt in options
        )
        rows.append(
            PreviewRow(
                item=None,
                label="One of",
                qty_min=None,
                qty_max=None,
                chance_pct=slot.chance_pct,
                options=preview_options,
                unknown=slot.unknown,
                masked=False,
            )
        )

    return rows


def _children(container):
    """Container items directly reachable through this container's slots."""

    result = []
    for slot in container.slots.all():
        for opt in slot.options.all():
            if opt.item.is_container:
                result.append(opt.item)
    return result


def _parents(container):
    """Containers that list ``container`` as one of their slot option items."""

    return {
        opt.slot.container
        for opt in ContainerSlotOption.objects.filter(item=container).select_related(
            "slot__container"
        )
    }


def _reaches_itself(container):
    """True if ``container`` is reachable from its own option items (a cycle)."""

    seen = set()
    stack = list(_children(container))
    while stack:
        current = stack.pop()
        if current.pk == container.pk:
            return True
        if current.pk in seen:
            continue
        seen.add(current.pk)
        stack.extend(_children(current))
    return False


def _down_depth(container, memo, visiting):
    """Longest container chain down from ``container``, counting ``container``."""

    if container.pk in memo:
        return memo[container.pk]
    if container.pk in visiting:
        return 1
    visiting.add(container.pk)
    best = 1
    for child in _children(container):
        best = max(best, 1 + _down_depth(child, memo, visiting))
    visiting.discard(container.pk)
    memo[container.pk] = best
    return best


def _up_depth(container, memo, visiting):
    """Longest container chain up through containers holding it, counting it."""

    if container.pk in memo:
        return memo[container.pk]
    if container.pk in visiting:
        return 1
    visiting.add(container.pk)
    best = 1
    for parent in _parents(container):
        best = max(best, 1 + _up_depth(parent, memo, visiting))
    visiting.discard(container.pk)
    memo[container.pk] = best
    return best


def validate_container_config(container):
    """Validate ``container``'s slot configuration.

    Raises :class:`~django.core.exceptions.ValidationError` with a list of
    messages when the config has a cycle, exceeds :data:`MAX_DEPTH`, has an
    empty slot, or references an item from another club.
    """

    errors = []
    club = container.club

    slots = list(container.slots.prefetch_related("options__item").order_by("position", "id"))
    if not slots:
        errors.append("A container must have at least one slot.")

    for slot in slots:
        options = list(slot.options.all())
        if not options:
            errors.append(f"Slot {slot.position} has no options.")
            continue
        for opt in options:
            if opt.item.club_id != club.id:
                errors.append(f'Item "{opt.item}" is not in the same club as the container.')

    if _reaches_itself(container):
        errors.append(f'Container "{container}" contains itself.')

    down = _down_depth(container, {}, set())
    up = _up_depth(container, {}, set())
    if down + up - 1 > MAX_DEPTH:
        errors.append(
            f"Container nesting depth {down + up - 1} exceeds the maximum of {MAX_DEPTH}."
        )

    if errors:
        raise ValidationError(errors)
