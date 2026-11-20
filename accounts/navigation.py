"""Registry of top-bar navigation entries (U29).

Each app registers entries from `apps.py` `ready()`. `check(request) -> bool`;
`None` means always shown. All club pages take the club slug.
"""

from typing import NamedTuple

from django.urls import reverse

GROUPS = ("primary", "character", "town", "map", "club", "account", "gm", "admin")

# Menu groups in display order: (key, heading). Read by the top bar and club home (U60).
MENU_GROUPS = (
    ("character", "Character"),
    ("town", "Town"),
    ("map", "Map"),
    ("club", "Club"),
    ("account", "Account"),
)


class NavEntry(NamedTuple):
    group: str
    label: str
    url_name: str
    check: object
    order: int
    icon: object = None
    shortcut_order: object = None
    shortcut_label: object = None
    also_current: tuple = ()


class NavLink(NamedTuple):
    label: str
    url: str
    url_name: str
    active: bool
    icon: object = None


_entries = []


def register(
    group,
    label,
    url_name,
    check=None,
    order=100,
    icon=None,
    shortcut_order=None,
    shortcut_label=None,
    also_current=(),
):
    if group not in GROUPS:
        raise ValueError(f"Unknown navigation group: {group!r}")
    for existing in _entries:
        if existing.group == group and existing.url_name == url_name:
            return existing
    entry = NavEntry(
        group, label, url_name, check, order, icon, shortcut_order, shortcut_label, also_current
    )
    _entries.append(entry)
    return entry


def entries_for(request):
    result = {group: [] for group in GROUPS}
    user = getattr(request, "user", None)
    club = getattr(request, "club", None)
    if club is None or user is None or not user.is_authenticated:
        return result
    match = getattr(request, "resolver_match", None)
    if match:
        # resolver_match.url_name is the local name; include namespace for comparison
        ns = match.namespace
        current = f"{ns}:{match.url_name}" if ns else match.url_name
    else:
        current = None
    shortcuts = []
    for entry in sorted(_entries, key=lambda e: (e.order, e.label)):
        if entry.check is not None and not entry.check(request):
            continue
        # Check if current matches entry.url_name or any of the also_current patterns
        # also_current entries can be short names ("club_home") or full names ("accounts:club_home")
        active = entry.url_name == current
        if not active:
            for alt in entry.also_current:
                if alt == current or (ns and alt == match.url_name):
                    active = True
                    break
        link = NavLink(
            entry.label,
            reverse(entry.url_name, args=[club.slug]),
            entry.url_name,
            active,
            entry.icon,
        )
        result[entry.group].append(link)
        if entry.icon and entry.group != "primary":
            key = entry.shortcut_order if entry.shortcut_order is not None else entry.order
            shortcuts.append((key, link._replace(label=entry.shortcut_label or link.label)))
    result["primary"].extend(link for _, link in sorted(shortcuts, key=lambda t: t[0]))
    return result
