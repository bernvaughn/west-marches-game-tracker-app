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


def band_label(band):
    return f"CR {band}" if band else ""


def xp_table(club):
    """The club's XPLevel rows in DEFAULT_XP_TABLE order (copies defaults lazily)."""
    copy_default_xp_table(club)
    rows = {r.band: r for r in XPLevel.objects.filter(club=club)}
    return [rows[band] for band, _d, _e in DEFAULT_XP_TABLE if band in rows]


def xp_for(club, band):
    """Return (discover_xp, explore_xp) for the band, or None for an empty band."""
    if not band:
        return None
    row = XPLevel.objects.filter(club=club, band=band).first()
    if row is None:
        copy_default_xp_table(club)
        row = XPLevel.objects.filter(club=club, band=band).first()
    return (row.discover_xp, row.explore_xp) if row else None
