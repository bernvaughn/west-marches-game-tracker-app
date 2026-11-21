"""Shared rename table for seeded item names (U148-U153).

VARIANT_RENAMES maps each old seeded item name to its clearer "Variant (Kind)"
form.  Used by the seed modules, the catch-up command and the tests, so there is
one source of truth for the new names.

No Django import: safe to import in non-Django test modules.
"""

MAP_CASE = "Map Case"
SCROLL_CASE = "Scroll Case"
OLD_MAP_CASE_NAMES = ("Case, Map or Scroll", "Map or Scroll Case")

VARIANT_RENAMES: dict[str, str] = {
    # Instruments -> "X (Musical Instrument)"
    # Plain Bard/Guard names and the Entertainer's variant names all collapse to
    # one record per instrument (shared targets, by design).
    "Lute": "Lute (Musical Instrument)",
    "Flute": "Flute (Musical Instrument)",
    "Lyre": "Lyre (Musical Instrument)",
    "Horn": "Horn (Musical Instrument)",
    "Musical Instrument (Lute)": "Lute (Musical Instrument)",
    "Musical Instrument (Flute)": "Flute (Musical Instrument)",
    "Musical Instrument (Lyre)": "Lyre (Musical Instrument)",
    "Musical Instrument (Horn)": "Horn (Musical Instrument)",
    "Musical Instrument (Drum)": "Drum (Musical Instrument)",
    "Instrument (lute)": "Lute (Musical Instrument)",
    # Arcane Focus -> "X (Arcane Focus)"
    "Arcane Focus (Crystal)": "Crystal (Arcane Focus)",
    "Arcane Focus (Orb)": "Orb (Arcane Focus)",
    "Arcane Focus (Rod)": "Rod (Arcane Focus)",
    "Arcane Focus (Staff)": "Staff (Arcane Focus)",
    "Arcane Focus (Wand)": "Wand (Arcane Focus)",
    # Druidic Focus -> "X (Druidic Focus)"
    "Druidic Focus (Sprig of Mistletoe)": "Sprig of Mistletoe (Druidic Focus)",
    "Druidic Focus (Staff)": "Staff (Druidic Focus)",
    "Druidic Focus (Yew Wand)": "Yew Wand (Druidic Focus)",
    # Holy Symbol -> "X (Holy Symbol)"
    "Holy Symbol (Amulet)": "Amulet (Holy Symbol)",
    "Holy Symbol (Emblem)": "Emblem (Holy Symbol)",
    "Holy Symbol (Reliquary)": "Reliquary (Holy Symbol)",
    # Artisan's Tools -> "X (Artisan's Tools)"
    # Variant word spelled exactly as the seeds spell it today.
    "Artisan's Tools (Brewer's)": "Brewer's (Artisan's Tools)",
    "Artisan's Tools (Calligrapher's)": "Calligrapher's (Artisan's Tools)",
    "Artisan's Tools (Carpenter's)": "Carpenter's (Artisan's Tools)",
    "Artisan's Tools (Leatherworker's)": "Leatherworker's (Artisan's Tools)",
    "Artisan's Tools (Mason's)": "Mason's (Artisan's Tools)",
    "Artisan's Tools (Potter's)": "Potter's (Artisan's Tools)",
    "Artisan's Tools (Smith's)": "Smith's (Artisan's Tools)",
    "Artisan's Tools (Tinker's)": "Tinker's (Artisan's Tools)",
    "Artisan's Tools (Weaver's)": "Weaver's (Artisan's Tools)",
    "Artisan's Tools (Woodcarver's)": "Woodcarver's (Artisan's Tools)",
    # Gaming Set -> "X (Gaming Set)"
    "Gaming Set (Dice)": "Dice (Gaming Set)",
    "Gaming Set (Playing Cards)": "Playing Cards (Gaming Set)",
    "Gaming Set (Dragonchess)": "Dragonchess (Gaming Set)",
}

# Optional subset: the 10 instrument keys, for merge logic in later stories.
INSTRUMENT_RENAMES = {
    old: new
    for old, new in VARIANT_RENAMES.items()
    if old
    in {
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
}
