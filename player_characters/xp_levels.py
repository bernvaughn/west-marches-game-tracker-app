"""Standard 5e XP thresholds and pure helpers for the character sheet.

The table is a constant: it is not editable per club.
"""

MAX_LEVEL = 20

# XP required to reach each level. Level 1 starts at 0 XP.
XP_THRESHOLDS = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}


def level_for_xp(xp):
    """Level reached by this XP: 1 at the start, capped at MAX_LEVEL."""
    level = 1
    for candidate in range(MAX_LEVEL, 0, -1):
        if xp >= XP_THRESHOLDS[candidate]:
            level = candidate
            break
    return level


def next_threshold(xp):
    """XP required for the next level, or None at MAX_LEVEL."""
    level = level_for_xp(xp)
    if level >= MAX_LEVEL:
        return None
    return XP_THRESHOLDS[level + 1]


def progress_fraction(xp):
    """Fraction of the current level span earned: 0.0 at the floor, 1.0 at max."""
    level = level_for_xp(xp)
    if level >= MAX_LEVEL:
        return 1.0
    floor = XP_THRESHOLDS[level]
    ceiling = XP_THRESHOLDS[level + 1]
    return (xp - floor) / (ceiling - floor)
