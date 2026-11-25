"""Helpers for the character sheet: ability modifiers, passive Perception and XP progress."""

from dataclasses import dataclass

from items.models import Item
from items.weights import format_weight, item_weight_total
from ledger.coins import display_parts, format_coins
from ledger.services import coin_balance, held_coins, held_items, item_quantities

from .models import ABILITIES
from .xp_levels import MAX_LEVEL, level_for_xp, next_threshold, progress_fraction

DASH = "—"
MINUS = "−"

ABILITY_FIELDS = {name for name, _abbr, _label in ABILITIES}


def edit_current_values(form):
    """Display text for the saved value of each field on the character edit form.

    The values come from form.saved_values (or form.initial), which hold the
    record as saved. A failed is_valid() has already copied the submitted
    values onto form.instance, so the instance is never safe to read here.
    """
    values = {}
    for name, value in getattr(form, "saved_values", form.initial).items():
        if name not in form.fields:
            continue
        if name in ABILITY_FIELDS:
            modifier = format_modifier(ability_modifier(value))
            values[name] = f"{value} ({modifier})" if value is not None else DASH
        elif value is None:
            values[name] = DASH
        elif isinstance(value, str):
            values[name] = value.strip() or DASH
        else:
            values[name] = str(value)
    return values


def ability_modifier(score):
    """D&D modifier for a score, or None when the score is blank."""
    if score is None:
        return None
    return (score - 10) // 2


def format_modifier(mod):
    if mod is None:
        return DASH
    return f"+{mod}" if mod >= 0 else f"{MINUS}{-mod}"


def passive_perception(bonus):
    """10 plus the bonus. None when the bonus is blank."""
    if bonus is None:
        return None
    return 10 + bonus


def passive_perception_label(bonus):
    if bonus is None:
        return DASH
    sign = "+" if bonus >= 0 else MINUS
    return f"{10 + bonus} (10 {sign} {abs(bonus)})"


def ability_rows(character):
    rows = []
    for field, abbr, label in ABILITIES:
        score = getattr(character, field)
        rows.append(
            {
                "field": field,
                "abbr": abbr,
                "label": label,
                "score": DASH if score is None else score,
                "modifier": format_modifier(ability_modifier(score)),
            }
        )
    return rows


def xp_progress(character):
    """XP progress for the sheet, or None when XP is blank.

    The bar is driven by XP alone. The stored level only drives the
    "level up ready" badge and the max-level check. The app never
    changes the level itself.
    """
    if character.xp is None:
        return None
    xp = character.xp
    level = character.level
    xp_level = level_for_xp(xp)
    threshold = next_threshold(xp)
    # "Max level" follows the stored level. A blank level falls back to XP.
    # A stored level below 20 with 355,000+ XP still gets the badge.
    if level is None:
        is_max = threshold is None
    else:
        is_max = level >= MAX_LEVEL
    level_up_ready = level is not None and level < xp_level
    progress = {
        "xp": xp,
        "xp_level": xp_level,
        "next_level": None if threshold is None else xp_level + 1,
        "next_threshold": threshold,
        "percent": int(progress_fraction(xp) * 100),
        "is_max": is_max,
        "level_up_ready": level_up_ready,
    }
    if threshold is not None:
        progress["xp_label"] = f"{xp:,} / {threshold:,} XP to level {xp_level + 1}"
    else:
        progress["xp_label"] = f"{xp:,} XP (level {MAX_LEVEL} reached)"
    return progress


@dataclass(frozen=True)
class InventoryRow:
    item: Item
    owned: int
    held: int

    @property
    def available(self):
        return self.owned - self.held


@dataclass(frozen=True)
class CoinSummary:
    owned: int
    held: int

    @property
    def available(self):
        return self.owned - self.held

    @property
    def parts(self):
        return list(zip(("pp", "gp", "sp", "cp"), display_parts(self.owned), strict=True))

    @property
    def has_holds(self):
        return self.held > 0


def inventory_rows(character):
    """Owned items (retired included), ordered by item name."""
    owned = {i: q for i, q in item_quantities(character).items() if q > 0}
    if not owned:
        return []
    held = held_items(character)
    items = Item.objects.filter(pk__in=owned).order_by("name", "pk")
    return [InventoryRow(item=i, owned=owned[i.pk], held=held.get(i.pk, 0)) for i in items]


def coin_summary(character):
    return CoinSummary(owned=coin_balance(character), held=held_coins(character))


def inventory_values(rows):
    """Compute base value and weight for each inventory row, in one pass.

    Reads already-fetched Item attributes (no extra queries). Returns a list of
    dicts parallel to ``rows`` with keys:
    value_cp, value_text, value_per_unit_text,
    weight_hundredths, weight_text, weight_per_unit_text.
    """
    out = []
    for row in rows:
        item = row.item
        units = row.owned

        # --- value (total and per-unit) ---
        if item.is_stacked:
            per_unit_cp = item.value_cp // item.value_units
            total_cp = per_unit_cp * units
        else:
            per_unit_cp = item.value_cp
            total_cp = item.value_cp
        value_text = format_coins(total_cp) if total_cp else "no value"
        value_per_unit_text = format_coins(per_unit_cp) if per_unit_cp else "no value"

        # --- weight (total and per-unit) ---
        total_hundredths = item_weight_total(item, units)
        if total_hundredths is None:
            weight_text = "—"
            weight_per_unit_text = "—"
        else:
            weight_text = format_weight(total_hundredths, precision=1)
            weight_per_unit_text = format_weight(item.weight_hundredth_lb, precision=1)

        out.append(
            {
                "value_cp": total_cp,
                "value_text": value_text,
                "value_per_unit_text": value_per_unit_text,
                "weight_hundredths": total_hundredths,
                "weight_text": weight_text,
                "weight_per_unit_text": weight_per_unit_text,
            }
        )
    return out
