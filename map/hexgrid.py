"""Axial hex grid maths (pointy-top)."""

import math

DEFAULT_RADIUS = 6
MAX_RADIUS = 15


def distance(q1, r1, q2, r2):
    dq, dr = q2 - q1, r2 - r1
    return (abs(dq) + abs(dq + dr) + abs(dr)) // 2


def window_positions(cq, cr, radius):
    out = []
    for dr in range(-radius, radius + 1):
        for dq in range(-radius, radius + 1):
            if distance(0, 0, dq, dr) <= radius:
                out.append((cq + dq, cr + dr))
    return sorted(out, key=lambda p: (p[1], p[0]))


def window_bounds(cq, cr, radius):
    return cq - radius, cq + radius, cr - radius, cr + radius


def to_pixel(q, r, size):
    return size * math.sqrt(3) * (q + r / 2), size * 1.5 * r


def hex_points(x, y, size):
    pts = []
    for i in range(6):
        a = math.radians(30 + 60 * i)
        pts.append(f"{x + size * math.cos(a):.2f},{y + size * math.sin(a):.2f}")
    return " ".join(pts)


DIRECTIONS = {"E": (1, 0), "W": (-1, 0), "NE": (1, -1), "NW": (0, -1), "SE": (0, 1), "SW": (-1, 1)}


def pan_links(cq, cr, radius):
    return {name: (cq + dq * radius, cr + dr * radius) for name, (dq, dr) in DIRECTIONS.items()}


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_window(params):
    q = _int(params.get("q"), 0)
    r = _int(params.get("r"), 0)
    radius = _int(params.get("radius"), DEFAULT_RADIUS)
    return q, r, max(1, min(MAX_RADIUS, radius))


# Coordinate text is COORD_FONT user units (see .hex-coord in map.css).
COORD_FONT = 10
MIN_TEXT_PX = 8
MIN_SCALE = MIN_TEXT_PX / COORD_FONT


def fit_svg(vb_w, vb_h, avail_w, avail_h, min_scale=MIN_SCALE):
    """Size in px that fits a viewBox into the space; never below min_scale.

    Returns (width, height, scrolls). scrolls is True when the minimum applies.
    """
    scale = min(avail_w / vb_w, avail_h / vb_h)
    scrolls = scale < min_scale
    if scrolls:
        scale = min_scale
    return vb_w * scale, vb_h * scale, scrolls
