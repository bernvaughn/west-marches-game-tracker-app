"""Orchestration of the per-club seeders run when a new club is created.

The seeders here are importable as module-level names of this module so
tests can monkeypatch ``accounts.club_seeding.<name>``.
"""

from character_options.services import seed_default_options
from map.xp import copy_default_xp_table
from starting_equipment.seeding import seed_default_starting_equipment


def seed_new_club(club) -> dict:
    """Seed a brand-new club with the data it needs to be usable on day one.

    Runs, in order:

    1. ``copy_default_xp_table`` - the club's XP bands.
    2. ``seed_default_options`` - species, character classes, backgrounds.
    3. ``seed_default_starting_equipment`` - the item catalogue and the
       active "2024 D&D Default" starting-equipment template.

    This function opens no transaction and creates no club admin. The caller
    owns both and must call this inside its own ``transaction.atomic()``
    block, so a seed failure rolls the whole operation back.

    Args:
        club: An accounts.Club instance, already created.

    Returns:
        dict: ``{"options": <seed_default_options result>,
                 "starting_equipment": <SeedSummary>}``.
    """
    copy_default_xp_table(club)
    options = seed_default_options(club)
    starting_equipment = seed_default_starting_equipment(club)
    return {
        "options": options,
        "starting_equipment": starting_equipment,
    }
