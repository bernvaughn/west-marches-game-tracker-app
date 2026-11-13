"""Wheel payload for a downtime result (D3). Pure geometry; no database writes."""

import math

COLOURS = [
    "var(--wm-shop-ocean-deep)",
    "var(--wm-shop-forest-deep)",
    "var(--wm-shop-ember-deep)",
    "var(--wm-shop-violet-deep)",
    "var(--wm-shop-parchment-deep)",
    "var(--wm-accent)",
    "var(--wm-info)",
    "var(--wm-success)",
    "var(--wm-warning)",
]
RADIUS = 100
SHORT_MAX = 12


def _point(angle):
    """Angle in degrees from 12 o'clock, clockwise."""
    rad = math.radians(angle)
    return RADIUS * math.sin(rad), -RADIUS * math.cos(rad)


def _path(start, end):
    if end - start >= 360:
        r = RADIUS
        return f"M 0 {-r} A {r} {r} 0 1 1 0 {r} A {r} {r} 0 1 1 0 {-r} Z"
    x1, y1 = _point(start)
    x2, y2 = _point(end)
    large = 1 if end - start > 180 else 0
    return f"M 0 0 L {x1:.2f} {y1:.2f} A {RADIUS} {RADIUS} 0 {large} 1 {x2:.2f} {y2:.2f} Z"


def _short(label):
    return label if len(label) <= SHORT_MAX else label[: SHORT_MAX - 1].rstrip() + "…"


def wheel_payload(result):
    """Return the wheel for `result`, or None if the chosen entry is gone."""
    if result.entry_id is None:
        return None
    entries = list(result.action.entries.all())
    ids = [e.pk for e in entries]
    if result.entry_id not in ids:
        return None
    total = sum(e.weight for e in entries)
    slices, start = [], 0.0
    for i, e in enumerate(entries):
        angle = e.weight * 360 / total
        end = 360.0 if i == len(entries) - 1 else start + angle
        mid = math.radians((start + end) / 2)
        slices.append(
            {
                "label": e.label,
                "short": _short(e.label),
                "weight": e.weight,
                "percent": round(e.weight * 100 / total, 1),
                "start": start,
                "end": end,
                "angle": angle,
                "colour": COLOURS[i % len(COLOURS)],
                "path": _path(start, end),
                "label_x": round(62 * math.sin(mid), 2),
                "label_y": round(-62 * math.cos(mid), 2),
                "label_rotate": round((start + end) / 2 - 90, 2),
            }
        )
        start = end
    chosen = ids.index(result.entry_id)
    s = slices[chosen]
    return {
        "chosen": chosen,
        "final_rotation": round((-(s["start"] + s["end"]) / 2) % 360, 3),
        "slices": slices,
    }
