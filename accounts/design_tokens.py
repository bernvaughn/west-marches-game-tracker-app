"""Read static/css/tokens.css for the design reference page and its tests (U35)."""

import re

from django.contrib.staticfiles import finders

_DECL = re.compile(r"(--wm-[a-z0-9-]+)\s*:\s*([^;]+);")


def read_tokens():
    """Return {name: value} for every --wm- custom property defined in tokens.css."""
    path = finders.find("css/tokens.css")
    with open(path, encoding="utf-8") as fh:
        return {n: v.strip() for n, v in _DECL.findall(fh.read())}


def _luminance(hex_colour):
    h = hex_colour.lstrip("#")
    chans = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(fg, bg):
    """WCAG contrast ratio of two #rrggbb colours."""
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def token_groups():
    """Group tokens for display: a list of (id, title, [token dicts])."""
    tokens = read_tokens()
    surface = tokens["--wm-surface"]
    groups = {
        "spacing": ("Spacing", lambda n: "-space-" in n),
        "type": (
            "Type",
            lambda n: (
                "-font-" in n
                or "-text-" in n
                and n.split("-")[-1] in {"xs", "sm", "md", "lg", "xl", "2xl", "3xl"}
                or "-leading-" in n
            ),
        ),
        "colour": (
            "Colour roles",
            lambda n: n.startswith("--wm-") and tokens[n].startswith("#") and "-coin-" not in n,
        ),
        "coins": ("Coins", lambda n: "-coin-" in n),
        "radius": ("Radii", lambda n: "-radius-" in n),
        "shadow": ("Shadows", lambda n: "-shadow-" in n),
        "focus": ("Focus ring", lambda n: "-focus-" in n),
        "size": ("Sizes", lambda n: "-size-" in n),
    }
    out, used = [], set()
    for gid, (title, test) in groups.items():
        rows = []
        for name, value in tokens.items():
            if name in used or not test(name):
                continue
            used.add(name)
            row = {"name": name, "value": value, "is_colour": value.startswith("#")}
            if row["is_colour"]:
                row["contrast"] = round(contrast_ratio(value, surface), 1)
            rows.append(row)
        out.append((gid, title, rows))
    rest = [{"name": n, "value": v, "is_colour": False} for n, v in tokens.items() if n not in used]
    if rest:
        out.append(("other", "Other", rest))
    return out
