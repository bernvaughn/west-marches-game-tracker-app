from .models import XPLevel

DEFAULT_XP_TABLE = [
    ("1-2", 75, 225),
    ("3-4", 200, 400),
    ("5-6", 2825, 8475),
    ("7-8", 5000, 15000),
    ("9-10", 7500, 22500),
    ("11-12", 9000, 27000),
    ("13-14", 10000, 30000),
    ("15-16", 13750, 41250),
    ("17-18", 17500, 52000),
    ("19-20", 22500, 67500),
]


def copy_default_xp_table(club):
    """Create missing XP bands for a club. Never overwrites existing (edited) rows."""
    for band, discover_xp, explore_xp in DEFAULT_XP_TABLE:
        XPLevel.objects.get_or_create(
            club=club, band=band, defaults={"discover_xp": discover_xp, "explore_xp": explore_xp}
        )
