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
PLAIN_TOOL_OLDS = {"Carpenter's Tools", "Calligrapher's Supplies"}
SHARED_TARGET_OLDS = INSTRUMENT_OLDS | PLAIN_TOOL_OLDS
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
    assert len(VARIANT_RENAMES) == 36


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
    """Every non-merge key has a unique target (merge groups share on purpose)."""
    seen: dict[str, str] = {}
    for old, new in VARIANT_RENAMES.items():
        if old in SHARED_TARGET_OLDS:
            continue
        assert new not in seen, f"{new!r} targeted by {old!r} and {seen[new]!r}"
        seen[new] = old


def test_instruments_collapse_to_five_targets():
    """Plain, variant and pack instrument names share one target per instrument."""
    instrument_targets = {new for old, new in VARIANT_RENAMES.items() if old in INSTRUMENT_OLDS}
    assert instrument_targets == INSTRUMENT_TARGETS


def test_plain_tools_merge_into_artisan_variants():
    """Plain tool items share a target with their artisan's tools variant."""
    assert VARIANT_RENAMES["Carpenter's Tools"] == "Carpenter's Tools (Artisan's Tools)"
    assert VARIANT_RENAMES["Calligrapher's Supplies"] == "Calligrapher's Supplies (Artisan's Tools)"
    assert VARIANT_RENAMES["Carpenter's Tools"] == VARIANT_RENAMES["Artisan's Tools (Carpenter's)"]
    assert (
        VARIANT_RENAMES["Calligrapher's Supplies"]
        == VARIANT_RENAMES["Artisan's Tools (Calligrapher's)"]
    )
    # Not artisan's tools: must stay out of the table.
    assert "Thieves' Tools" not in VARIANT_RENAMES
    assert "Navigator's Tools" not in VARIANT_RENAMES


def test_artisan_targets_exact():
    expected = {
        "Brewer's Supplies",
        "Calligrapher's Supplies",
        "Carpenter's Tools",
        "Leatherworker's Tools",
        "Mason's Tools",
        "Potter's Tools",
        "Smith's Tools",
        "Tinker's Tools",
        "Weaver's Tools",
        "Woodcarver's Tools",
    }
    targets = {new for old, new in VARIANT_RENAMES.items() if old.startswith("Artisan's Tools (")}
    assert targets == {f"{n} (Artisan's Tools)" for n in expected}


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
        "Carpenter's Tools",
        "Calligrapher's Supplies",
        # Gaming Set
        "Gaming Set (Dice)",
        "Gaming Set (Playing Cards)",
        "Gaming Set (Dragonchess)",
    }
    assert expected_old <= set(VARIANT_RENAMES)
