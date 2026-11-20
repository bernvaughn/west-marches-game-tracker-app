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
        background_entry__template__club=club, item__name="Artisan's Tools (Woodcarver's)"
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
    tools = {name: qty for name, qty in granted.items() if name.startswith("Artisan's Tools")}
    assert tools == {"Artisan's Tools (Woodcarver's)": 1}
    assert granted["Mace"] == 1 and "Warhammer" not in granted

    # A second forced run is stable.
    before = _counts()
    seed_default_starting_equipment(club, force=True)
    assert _counts() == before
