"""Choice groups and pack containers in the default starting equipment seed."""

from collections import Counter

import pytest
from django.core.management import call_command

from accounts.models import Membership
from character_options.models import Background, CharacterClass
from items.models import ContainerSlot, ContainerSlotOption, Item
from items.pack_seeding import PACKS
from ledger.models import LedgerLine
from player_characters.models import Character
from starting_equipment.models import (
    StartingEquipmentBackgroundEntry,
    StartingEquipmentBackgroundLine,
    StartingEquipmentClassEntry,
    StartingEquipmentClassLine,
    StartingEquipmentTemplate,
)
from starting_equipment.seeding import (
    BACKGROUND_EQUIPMENT,
    CLASS_EQUIPMENT,
    DEFAULT_TEMPLATE_NAME,
    seed_default_starting_equipment,
)
from starting_equipment.services import apply_starting_equipment

# Every 2024 PHB class has at least one "X or Y" in its starting equipment.
CLASSES_WITH_CHOICES = [
    "Barbarian",
    "Bard",
    "Cleric",
    "Druid",
    "Fighter",
    "Monk",
    "Paladin",
    "Ranger",
    "Rogue",
    "Sorcerer",
    "Warlock",
    "Wizard",
]
# Backgrounds where the PHB lets the player pick a tool/instrument/gaming set.
BACKGROUNDS_WITH_CHOICES = {"Artisan", "Entertainer", "Soldier"}

ALL_ENTRIES = [("class", name, data) for name, data in CLASS_EQUIPMENT.items()] + [
    ("background", name, data) for name, data in BACKGROUND_EQUIPMENT.items()
]


def _groups(items):
    """Return {group: [item names in order]} for the choice lines of one entry."""
    groups = {}
    for name, *_rest, is_choice, group in items:
        if is_choice:
            groups.setdefault(group, []).append(name)
    return groups


def _expected_grant(items):
    """Counter of item name -> quantity a claim grants: fixed lines + first of each group."""
    expected = Counter()
    seen = set()
    for name, _v, _s, _r, _m, qty, is_choice, group in items:
        if is_choice:
            if group in seen:
                continue
            seen.add(group)
        expected[name] += qty
    return expected


def _counts():
    return (
        Item.objects.count(),
        StartingEquipmentClassLine.objects.count(),
        StartingEquipmentBackgroundLine.objects.count(),
        ContainerSlot.objects.count(),
        ContainerSlotOption.objects.count(),
    )


# ---------------------------------------------------------------------------
# Data integrity (no database)
# ---------------------------------------------------------------------------


def test_every_class_has_choice_groups():
    assert sorted(CLASS_EQUIPMENT) == sorted(CLASSES_WITH_CHOICES)
    for class_name in CLASSES_WITH_CHOICES:
        assert _groups(CLASS_EQUIPMENT[class_name]["items"]), class_name


def test_backgrounds_with_choice_groups():
    with_groups = {name for name, data in BACKGROUND_EQUIPMENT.items() if _groups(data["items"])}
    assert with_groups == BACKGROUNDS_WITH_CHOICES


@pytest.mark.parametrize(
    ("kind", "name", "data"), ALL_ENTRIES, ids=[f"{k}-{n}" for k, n, _ in ALL_ENTRIES]
)
def test_entry_data_integrity(kind, name, data):
    items = data["items"]
    for group, options in _groups(items).items():
        assert group, f"{kind} {name}: choice line without a group"
        assert len(group) <= 50
        assert len(options) >= 2, f"{kind} {name}: group {group!r} has one option"

    # An item is never listed twice in one group, nor twice as a fixed line.
    keys = [(item[0], item[7]) for item in items]
    assert len(keys) == len(set(keys)), f"{kind} {name}: duplicate line"

    # A group default (or any option) is never also a fixed line: that grants it twice.
    fixed = {item[0] for item in items if not item[6]}
    in_groups = {item[0] for item in items if item[6]}
    assert not fixed & in_groups, f"{kind} {name}: {fixed & in_groups} fixed and in a group"

    # Fixed lines never carry a group name.
    assert all(item[7] == "" for item in items if not item[6])


# ---------------------------------------------------------------------------
# Seeded template
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_seeded_template_has_choice_groups(club):
    seed_default_starting_equipment(club)
    for class_name in CLASSES_WITH_CHOICES:
        entry = StartingEquipmentClassEntry.objects.get(
            template__club=club, class_option__name=class_name
        )
        groups = Counter(entry.lines.filter(is_choice=True).values_list("choice_group", flat=True))
        assert groups, class_name
        assert all(group and n >= 2 for group, n in groups.items()), (class_name, groups)
    for bg_name in BACKGROUNDS_WITH_CHOICES:
        entry = StartingEquipmentBackgroundEntry.objects.get(
            template__club=club, background_option__name=bg_name
        )
        assert entry.lines.filter(is_choice=True).count() >= 2, bg_name


@pytest.mark.django_db
def test_packs_are_containers_after_first_run(club):
    summary = seed_default_starting_equipment(club)
    assert summary.packs_configured == len(PACKS)
    for pack_name, contents in PACKS.items():
        pack = Item.objects.get(club=club, name=pack_name)
        assert pack.is_container, pack_name
        assert pack.slots.count() == len(contents), pack_name


@pytest.mark.django_db
@pytest.mark.parametrize("force", [False, True])
def test_second_run_adds_nothing(club, force):
    seed_default_starting_equipment(club)
    before = _counts()
    line_ids = set(StartingEquipmentClassLine.objects.values_list("id", flat=True))
    line_ids |= set(StartingEquipmentBackgroundLine.objects.values_list("id", flat=True))

    summary = seed_default_starting_equipment(club, force=force)

    assert summary.items_created == 0
    assert summary.packs_configured == 0
    assert _counts() == before
    after_ids = set(StartingEquipmentClassLine.objects.values_list("id", flat=True))
    after_ids |= set(StartingEquipmentBackgroundLine.objects.values_list("id", flat=True))
    assert after_ids == line_ids  # a forced run does not rebuild matching lines


@pytest.mark.django_db
@pytest.mark.parametrize("args", [[], ["--force"]])
def test_second_command_run_adds_nothing(club, args):
    call_command("seed_starting_equipment", "--club", club.slug)
    before = _counts()
    call_command("seed_starting_equipment", "--club", club.slug, *args)
    assert _counts() == before


# ---------------------------------------------------------------------------
# End-to-end claim on the seeded template
# ---------------------------------------------------------------------------


def _claim(club, player, class_name, bg_name):
    template = StartingEquipmentTemplate.objects.get(club=club, name=DEFAULT_TEMPLATE_NAME)
    character = Character.objects.create(
        club=club,
        owner=Membership.objects.get(user=player, club=club),
        name=f"{class_name} {bg_name}",
        char_class=class_name,
        class_option=CharacterClass.objects.get(club=club, name=class_name),
        background=bg_name,
        background_option=Background.objects.get(club=club, name=bg_name),
        level=1,
    )
    result = apply_starting_equipment(character, template, None)
    assert result.entry is not None
    granted = Counter()
    for line in LedgerLine.objects.filter(entry=result.entry, item__isnull=False):
        granted[line.item.name] += line.quantity
    return granted


@pytest.mark.django_db
@pytest.mark.parametrize("class_name", CLASSES_WITH_CHOICES)
def test_claim_grants_exactly_one_option_per_class_group(club, player, class_name):
    seed_default_starting_equipment(club)
    granted = _claim(club, player, class_name, "Acolyte")

    expected = _expected_grant(CLASS_EQUIPMENT[class_name]["items"])
    expected += _expected_grant(BACKGROUND_EQUIPMENT["Acolyte"]["items"])
    assert granted == expected

    # Every class starts with exactly one pack (the old seed granted two).
    assert sum(qty for name, qty in granted.items() if name in PACKS) == 1, granted

    # Only the first option of each group is granted.
    for options in _groups(CLASS_EQUIPMENT[class_name]["items"]).values():
        assert options[0] in granted
        for name in options[1:]:
            assert granted[name] == expected[name], (class_name, name)


@pytest.mark.django_db
def test_cleric_claim_gets_one_of_each(club, player):
    """Guards the double-grant bug: a Cleric gets one weapon, armor, ranged and pack."""
    seed_default_starting_equipment(club)
    granted = _claim(club, player, "Cleric", "Acolyte")
    assert granted["Mace"] == 1 and "Warhammer" not in granted
    assert granted["Scale Mail"] == 1 and "Leather Armor" not in granted
    assert "Chain Mail" not in granted
    assert granted["Light Crossbow"] == 1 and "Shortbow" not in granted
    assert granted["Priest's Pack"] == 1 and "Explorer's Pack" not in granted


@pytest.mark.django_db
@pytest.mark.parametrize("bg_name", sorted(BACKGROUNDS_WITH_CHOICES))
def test_claim_grants_one_option_per_background_group(club, player, bg_name):
    seed_default_starting_equipment(club)
    granted = _claim(club, player, "Fighter", bg_name)
    expected = _expected_grant(CLASS_EQUIPMENT["Fighter"]["items"])
    expected += _expected_grant(BACKGROUND_EQUIPMENT[bg_name]["items"])
    assert granted == expected
    for options in _groups(BACKGROUND_EQUIPMENT[bg_name]["items"]).values():
        assert [name for name in options if name in granted] == [options[0]]


# ---------------------------------------------------------------------------
# Upgrading an existing (pre-choice-group) template with --force
# ---------------------------------------------------------------------------


def _downgrade_to_old_style(club):
    """Rewrite the seeded template to look like the old seed: no choice lines.

    The old seed had every group default as a fixed line, no alternatives, and
    a single generic "Artisan's Tools" item for the Artisan background.
    """
    for line_model, entry_field in (
        (StartingEquipmentClassLine, "class_entry"),
        (StartingEquipmentBackgroundLine, "background_entry"),
    ):
        lines = line_model.objects.filter(**{f"{entry_field}__template__club": club})
        seen = set()
        for line in lines.filter(is_choice=True).order_by("id"):
            key = (getattr(line, f"{entry_field}_id"), line.choice_group)
            if key in seen:
                line.delete()
            else:
                seen.add(key)
                line.is_choice = False
                line.choice_group = ""
                line.save()
    old_tools = Item.objects.create(club=club, name="Artisan's Tools", value_cp=2000)
    StartingEquipmentBackgroundLine.objects.filter(
        background_entry__template__club=club, item__name="Woodcarver's Tools (Artisan's Tools)"
    ).update(item=old_tools)


def _lines_as_data(entry_lines):
    return [
        (line.item.name, line.quantity, line.is_choice, line.choice_group)
        for line in entry_lines.select_related("item").order_by("id")
    ]


def _data_as_lines(items):
    return [(item[0], item[5], item[6], item[7]) for item in items]


@pytest.mark.django_db
def test_force_upgrades_old_style_template(club, player):
    seed_default_starting_equipment(club)
    _downgrade_to_old_style(club)
    assert not StartingEquipmentClassLine.objects.filter(is_choice=True).exists()

    # A plain run leaves the old template alone.
    assert seed_default_starting_equipment(club).skipped is True
    assert not StartingEquipmentClassLine.objects.filter(is_choice=True).exists()

    seed_default_starting_equipment(club, force=True)

    for class_name, data in CLASS_EQUIPMENT.items():
        entry = StartingEquipmentClassEntry.objects.get(
            template__club=club, class_option__name=class_name
        )
        assert _lines_as_data(entry.lines) == _data_as_lines(data["items"]), class_name
    for bg_name, data in BACKGROUND_EQUIPMENT.items():
        entry = StartingEquipmentBackgroundEntry.objects.get(
            template__club=club, background_option__name=bg_name
        )
        assert _lines_as_data(entry.lines) == _data_as_lines(data["items"]), bg_name

    # The stale generic tools line is gone, so an Artisan gets exactly one tool.
    granted = _claim(club, player, "Cleric", "Artisan")
    tools = {name: qty for name, qty in granted.items() if name.endswith("(Artisan's Tools)")}
    assert tools == {"Woodcarver's Tools (Artisan's Tools)": 1}
    assert granted["Mace"] == 1 and "Warhammer" not in granted

    # A second forced run is stable.
    before = _counts()
    seed_default_starting_equipment(club, force=True)
    assert _counts() == before


# ---------------------------------------------------------------------------
# New tests for U150/U151 variant name changes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_seed_module_has_no_old_names():
    """The seed module text must not contain any old name from VARIANT_RENAMES."""
    import re
    from pathlib import Path

    from items.seed_names import VARIANT_RENAMES

    seed_path = Path(__file__).parent.parent / "seeding.py"
    text = seed_path.read_text()

    for old_name in VARIANT_RENAMES.keys():
        pattern = re.escape(f'"{old_name}"') + "|" + re.escape(f"'{old_name}'")
        assert not re.search(pattern, text), f"Old name {old_name!r} found in seeding.py"


@pytest.mark.django_db
def test_every_renamed_family_appears(club):
    """Every renamed family appears under its new name in the seeded data."""
    from items.seed_names import VARIANT_RENAMES

    seed_default_starting_equipment(club)

    # Collect all seeded item names
    all_names = set(Item.objects.for_club(club).values_list("name", flat=True))

    # Expected new names per family
    expected_families = {
        "Musical Instrument": [
            "Lute (Musical Instrument)",
            "Flute (Musical Instrument)",
            "Lyre (Musical Instrument)",
            "Horn (Musical Instrument)",
            "Drum (Musical Instrument)",
        ],
        "Arcane Focus": [
            "Crystal (Arcane Focus)",
            "Orb (Arcane Focus)",
            "Rod (Arcane Focus)",
            "Staff (Arcane Focus)",
            "Wand (Arcane Focus)",
        ],
        "Druidic Focus": [
            "Staff (Druidic Focus)",
        ],
        "Holy Symbol": [
            "Amulet (Holy Symbol)",
        ],
        "Artisan's Tools": [
            "Woodcarver's Tools (Artisan's Tools)",
            "Brewer's Supplies (Artisan's Tools)",
            "Calligrapher's Supplies (Artisan's Tools)",
            "Carpenter's Tools (Artisan's Tools)",
            "Leatherworker's Tools (Artisan's Tools)",
            "Mason's Tools (Artisan's Tools)",
            "Potter's Tools (Artisan's Tools)",
            "Smith's Tools (Artisan's Tools)",
            "Tinker's Tools (Artisan's Tools)",
            "Weaver's Tools (Artisan's Tools)",
        ],
        "Gaming Set": [
            "Dice (Gaming Set)",
            "Playing Cards (Gaming Set)",
            "Dragonchess (Gaming Set)",
        ],
    }

    # Every expected new name must be present
    for family, names in expected_families.items():
        for name in names:
            assert name in all_names, f"Missing {family} variant: {name}"

    # Every seeded name that is a renamed variant must be a VARIANT_RENAMES value
    # (or a non-renamed item like Navigator's Tools, Thieves' Tools, etc.)
    renamed_values = set(VARIANT_RENAMES.values())
    for name in all_names:
        if (
            name.endswith("(Musical Instrument)")
            or name.endswith("(Arcane Focus)")
            or name.endswith("(Druidic Focus)")
            or name.endswith("(Holy Symbol)")
            or name.endswith("(Artisan's Tools)")
            or name.endswith("(Gaming Set)")
        ):
            assert name in renamed_values, f"Seeded name {name!r} not in VARIANT_RENAMES values"


@pytest.mark.django_db
def test_instruments_share_one_record(club):
    """Bard, Entertainer, and Guard share one record per instrument."""
    seed_default_starting_equipment(club)

    instrument_names = [
        "Lute (Musical Instrument)",
        "Flute (Musical Instrument)",
        "Lyre (Musical Instrument)",
        "Horn (Musical Instrument)",
    ]

    for name in instrument_names:
        items = Item.objects.filter(club=club, name=name)
        assert items.count() == 1, f"Expected 1 record for {name}, got {items.count()}"

    # Old plain names should not exist as Items
    for old_name in ["Lute", "Flute", "Lyre", "Horn"]:
        assert not Item.objects.filter(club=club, name=old_name).exists(), (
            f"Old name {old_name!r} should not exist as an Item"
        )

    # Re-seed: second run must keep count == 1
    seed_default_starting_equipment(club, force=True)
    for name in instrument_names:
        assert Item.objects.filter(club=club, name=name).count() == 1


@pytest.mark.django_db
def test_drum_only_in_entertainer(club):
    """Drum is in the Entertainer's choice group, not in the Bard's."""
    seed_default_starting_equipment(club)

    # Bard has no Drum in its instrument group
    bard_entry = StartingEquipmentClassEntry.objects.get(
        template__club=club, class_option__name="Bard"
    )
    bard_instruments = bard_entry.lines.filter(choice_group="instrument").values_list(
        "item__name", flat=True
    )
    assert "Drum (Musical Instrument)" not in bard_instruments
    assert set(bard_instruments) == {
        "Lute (Musical Instrument)",
        "Flute (Musical Instrument)",
        "Lyre (Musical Instrument)",
        "Horn (Musical Instrument)",
    }

    # Entertainer has Drum
    ent_entry = StartingEquipmentBackgroundEntry.objects.get(
        template__club=club, background_option__name="Entertainer"
    )
    ent_instruments = ent_entry.lines.filter(choice_group="instrument").values_list(
        "item__name", flat=True
    )
    assert "Drum (Musical Instrument)" in ent_instruments
    assert set(ent_instruments) == {
        "Lute (Musical Instrument)",
        "Flute (Musical Instrument)",
        "Lyre (Musical Instrument)",
        "Horn (Musical Instrument)",
        "Drum (Musical Instrument)",
    }


@pytest.mark.django_db
def test_farmer_and_scribe_share_artisan_records(club):
    """Farmer's Carpenter and Scribe's Calligrapher are the Artisan's records."""
    seed_default_starting_equipment(club)

    # Farmer's line item == Artisan's Carpenter line item
    farmer_entry = StartingEquipmentBackgroundEntry.objects.get(
        template__club=club, background_option__name="Farmer"
    )
    farmer_tool = farmer_entry.lines.first().item
    assert farmer_tool.name == "Carpenter's Tools (Artisan's Tools)"

    artisan_entry = StartingEquipmentBackgroundEntry.objects.get(
        template__club=club, background_option__name="Artisan"
    )
    artisan_carpenter = (
        artisan_entry.lines.filter(item__name="Carpenter's Tools (Artisan's Tools)").first().item
    )
    assert farmer_tool.pk == artisan_carpenter.pk

    # Scribe's line item == Artisan's Calligrapher line item
    scribe_entry = StartingEquipmentBackgroundEntry.objects.get(
        template__club=club, background_option__name="Scribe"
    )
    scribe_tool = scribe_entry.lines.first().item
    assert scribe_tool.name == "Calligrapher's Supplies (Artisan's Tools)"

    artisan_calligrapher = (
        artisan_entry.lines.filter(item__name="Calligrapher's Supplies (Artisan's Tools)")
        .first()
        .item
    )
    assert scribe_tool.pk == artisan_calligrapher.pk

    # Exactly one record each
    assert Item.objects.filter(club=club, name="Carpenter's Tools (Artisan's Tools)").count() == 1
    assert (
        Item.objects.filter(club=club, name="Calligrapher's Supplies (Artisan's Tools)").count()
        == 1
    )


@pytest.mark.django_db
def test_choice_slugs_and_order_unchanged(club):
    """Choice group slugs and line order (first = default) are unchanged."""
    seed_default_starting_equipment(club)

    # Helper to get distinct choice groups in order of appearance
    def get_groups(entry):
        seen = set()
        groups = []
        for line in entry.lines.filter(is_choice=True).order_by("id"):
            if line.choice_group not in seen:
                seen.add(line.choice_group)
                groups.append(line.choice_group)
        return groups

    # Bard: weapon, pack, instrument (ordered by line id)
    bard_entry = StartingEquipmentClassEntry.objects.get(
        template__club=club, class_option__name="Bard"
    )
    bard_groups = get_groups(bard_entry)
    assert bard_groups == ["weapon", "pack", "instrument"]
    # First instrument is Lute (default)
    first_instrument = bard_entry.lines.filter(choice_group="instrument").order_by("id").first()
    assert first_instrument.item.name == "Lute (Musical Instrument)"

    # Entertainer: instrument
    ent_entry = StartingEquipmentBackgroundEntry.objects.get(
        template__club=club, background_option__name="Entertainer"
    )
    ent_groups = get_groups(ent_entry)
    assert ent_groups == ["instrument"]
    first_ent_instrument = ent_entry.lines.filter(choice_group="instrument").order_by("id").first()
    assert first_ent_instrument.item.name == "Lute (Musical Instrument)"

    # Artisan: tools
    art_entry = StartingEquipmentBackgroundEntry.objects.get(
        template__club=club, background_option__name="Artisan"
    )
    art_groups = get_groups(art_entry)
    assert art_groups == ["tools"]
    first_tool = art_entry.lines.filter(choice_group="tools").order_by("id").first()
    assert first_tool.item.name == "Woodcarver's Tools (Artisan's Tools)"

    # Soldier: gaming_set
    sol_entry = StartingEquipmentBackgroundEntry.objects.get(
        template__club=club, background_option__name="Soldier"
    )
    sol_groups = get_groups(sol_entry)
    assert sol_groups == ["gaming_set"]
    first_gaming = sol_entry.lines.filter(choice_group="gaming_set").order_by("id").first()
    assert first_gaming.item.name == "Dice (Gaming Set)"

    # Wizard/Sorcerer/Warlock: focus (first is Crystal)
    for class_name in ["Wizard", "Sorcerer", "Warlock"]:
        cls_entry = StartingEquipmentClassEntry.objects.get(
            template__club=club, class_option__name=class_name
        )
        cls_groups = get_groups(cls_entry)
        assert "focus" in cls_groups
        first_focus = cls_entry.lines.filter(choice_group="focus").order_by("id").first()
        assert first_focus.item.name == "Component Pouch"


@pytest.mark.django_db
def test_bard_claim_defaults_to_lute_and_can_pick_others(club, player):
    """A Bard claim grants Lute by default and offers Flute, Lyre, Horn."""
    seed_default_starting_equipment(club)

    template = StartingEquipmentTemplate.objects.get(club=club, name=DEFAULT_TEMPLATE_NAME)
    character = Character.objects.create(
        club=club,
        owner=Membership.objects.get(user=player, club=club),
        name="Test Bard",
        char_class="Bard",
        class_option=CharacterClass.objects.get(club=club, name="Bard"),
        background="Acolyte",
        background_option=Background.objects.get(club=club, name="Acolyte"),
        level=1,
    )
    result = apply_starting_equipment(character, template, None)

    granted = Counter()
    for line in LedgerLine.objects.filter(entry=result.entry, item__isnull=False):
        granted[line.item.name] += line.quantity

    # Default grant includes Lute
    assert "Lute (Musical Instrument)" in granted
    assert granted["Lute (Musical Instrument)"] == 1

    # Other instruments NOT granted by default
    for name in [
        "Flute (Musical Instrument)",
        "Lyre (Musical Instrument)",
        "Horn (Musical Instrument)",
    ]:
        assert granted[name] == 0

    # The choice lines for Bard's instrument group offer Flute, Lyre, Horn
    instrument_lines = (
        StartingEquipmentClassLine.objects.for_club(club)
        .filter(class_entry__class_option__name="Bard", choice_group="instrument")
        .order_by("id")
    )
    offered = [line.item.name for line in instrument_lines]
    assert offered == [
        "Lute (Musical Instrument)",
        "Flute (Musical Instrument)",
        "Lyre (Musical Instrument)",
        "Horn (Musical Instrument)",
    ]
