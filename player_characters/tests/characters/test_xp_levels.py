"""Unit tests for the 5e XP threshold table. No DB needed."""

import pytest

from player_characters.xp_levels import (
    MAX_LEVEL,
    XP_THRESHOLDS,
    level_for_xp,
    next_threshold,
    progress_fraction,
)


def test_threshold_table_covers_levels_1_to_20():
    assert list(XP_THRESHOLDS) == list(range(1, MAX_LEVEL + 1))
    assert XP_THRESHOLDS[1] == 0
    assert XP_THRESHOLDS[2] == 300
    assert XP_THRESHOLDS[20] == 355000


@pytest.mark.parametrize(
    "xp,expected",
    [
        (0, 1),
        (299, 1),
        (300, 2),
        (899, 2),
        (900, 3),
        (2699, 3),
        (2700, 4),
        (6499, 4),
        (6500, 5),
        (13999, 5),
        (14000, 6),
        (354999, 19),
        (355000, 20),
        (999999, 20),
    ],
)
def test_level_for_xp_boundaries(xp, expected):
    assert level_for_xp(xp) == expected


def test_next_threshold():
    assert next_threshold(0) == 300
    assert next_threshold(299) == 300
    assert next_threshold(6500) == 14000
    assert next_threshold(13999) == 14000
    assert next_threshold(355000) is None
    assert next_threshold(999999) is None


@pytest.mark.parametrize(
    "xp,expected",
    [
        (0, 0.0),
        (300, 0.0),
        (6500, 0.0),
        (10250, 0.5),  # midpoint of the level 5 span (6,500 -> 14,000)
        (13999, pytest.approx(7499 / 7500)),
        (355000, 1.0),
        (999999, 1.0),
    ],
)
def test_progress_fraction(xp, expected):
    assert progress_fraction(xp) == expected
