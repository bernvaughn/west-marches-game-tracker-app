"""Tests for items/seed_names.py (no DB).

Covers the VARIANT_RENAMES table and the map/scroll case constants.
"""

import re

from items.seed_names import (
    MAP_CASE,
    OLD_MAP_CASE_NAMES,
    SCROLL_CASE,
    VARIANT_RENAMES,
)

VARIANT_RE = re.compile(r"^[^()]+ \([^()]+\)$")

INSTRUMENT_OLDS = {
    "Lute",
    "Flute",
    "Lyre",
    "Horn",
    "Musical Instrument (Lute)",
    "Musical Instrument (Flute)",
    "Musical Instrument (Lyre)",
    "Musical Instrument (Horn)",
    "Musical Instrument (Drum)",
    "Instrument (lute)",
}
INSTRUMENT_TARGETS = {
    "Lute (Musical Instrument)",
    "Flute (Musical Instrument)",
    "Lyre (Musical Instrument)",
    "Horn (Musical Instrument)",
    "Drum (Musical Instrument)",
}


def test_constants_exact():
    assert MAP_CASE == "Map Case"
    assert SCROLL_CASE == "Scroll Case"
    assert OLD_MAP_CASE_NAMES == ("Case, Map or Scroll", "Map or Scroll Case")


def test_table_is_not_empty():
    assert len(VARIANT_RENAMES) == 34


def test_every_value_matches_variant_kind():
    for old, new in VARIANT_RENAMES.items():
        assert VARIANT_RE.match(new), f"{old!r} -> {new!r} does not match Variant (Kind)"


def test_no_key_equals_its_value():
    for old, new in VARIANT_RENAMES.items():
        assert old != new, f"{old!r} maps to itself"


def test_no_key_is_a_target():
    targets = set(VARIANT_RENAMES.values())
    for old in VARIANT_RENAMES:
        assert old not in targets, f"{old!r} is also a target"


def test_non_instrument_targets_unique():
    """Every non-instrument family has a unique target."""
    seen: dict[str, str] = {}
    for old, new in VARIANT_RENAMES.items():
        if old in INSTRUMENT_OLDS:
            continue
        assert new not in seen, f"{new!r} targeted by {old!r} and {seen[new]!r}"
        seen[new] = old


def test_instruments_collapse_to_five_targets():
    """Plain, variant and pack instrument names share one target per instrument."""
    instrument_targets = {new for old, new in VARIANT_RENAMES.items() if old in INSTRUMENT_OLDS}
    assert instrument_targets == INSTRUMENT_TARGETS


def test_all_10_instrument_keys_present():
    assert INSTRUMENT_OLDS <= set(VARIANT_RENAMES)


def test_families_covered():
    """Every renamed family from the seed modules has a table key."""
    expected_old = {
        # Arcane Focus
        "Arcane Focus (Crystal)",
        "Arcane Focus (Orb)",
        "Arcane Focus (Rod)",
        "Arcane Focus (Staff)",
        "Arcane Focus (Wand)",
        # Druidic Focus
        "Druidic Focus (Sprig of Mistletoe)",
        "Druidic Focus (Staff)",
        "Druidic Focus (Yew Wand)",
        # Holy Symbol
        "Holy Symbol (Amulet)",
        "Holy Symbol (Emblem)",
        "Holy Symbol (Reliquary)",
        # Artisan's Tools
        "Artisan's Tools (Brewer's)",
        "Artisan's Tools (Calligrapher's)",
        "Artisan's Tools (Carpenter's)",
        "Artisan's Tools (Leatherworker's)",
        "Artisan's Tools (Mason's)",
        "Artisan's Tools (Potter's)",
        "Artisan's Tools (Smith's)",
        "Artisan's Tools (Tinker's)",
        "Artisan's Tools (Weaver's)",
        "Artisan's Tools (Woodcarver's)",
        # Gaming Set
        "Gaming Set (Dice)",
        "Gaming Set (Playing Cards)",
        "Gaming Set (Dragonchess)",
    }
    assert expected_old <= set(VARIANT_RENAMES)
