"""Registry of top-bar navigation entries (U29).

Each app registers entries from `apps.py` `ready()`. `check(request) -> bool`;
`None` means always shown. All club pages take the club slug unless
`club_required=False` is passed.
"""

from typing import NamedTuple

from django.urls import reverse

GROUPS = ("primary", "character", "town", "map", "club", "account", "gm", "admin")

# Menu groups in display order: (key, heading, icon). Read by the top bar and club home (U60).
MENU_GROUPS = (
    ("character", "Character", "person"),
    ("town", "Town", "shop"),
    ("map", "Map", "map"),
    ("club", "Club", "people"),
    ("account", "Account", "gear"),
    ("gm", "Game Master", "person-gear"),
    ("admin", "Club Admin", "gear-fill"),
)


class NavEntry(NamedTuple):
    group: str
    # label is either a static string or a callable(request) -> str so the
    # label can be computed per request (e.g. a dynamic count).
    label: object
    url_name: str
    check: object
    order: int
    icon: object = None
    shortcut_order: object = None
    shortcut_label: object = None
    also_current: tuple = ()
    club_required: bool = True


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
    club_required=True,
):
    if group not in GROUPS:
        raise ValueError(f"Unknown navigation group: {group!r}")
    for existing in _entries:
        if existing.group == group and existing.url_name == url_name:
            return existing
    entry = NavEntry(
        group,
        label,
        url_name,
        check,
        order,
        icon,
        shortcut_order,
        shortcut_label,
        also_current,
        club_required,
    )
    _entries.append(entry)
    return entry


def entries_for(request):
    result = {group: [] for group in GROUPS}
    user = getattr(request, "user", None)
    club = getattr(request, "club", None)
    if user is None or not user.is_authenticated:
        return result
    # For account links, we don't need a club
    has_club = club is not None
    match = getattr(request, "resolver_match", None)
    # Compare full names ("shops:index"), so entries in a namespace can match.
    current = match.view_name if match else None
    shortcuts = []
    for entry in sorted(
        _entries, key=lambda e: (e.order, e.label if isinstance(e.label, str) else "")
    ):
        if entry.check is not None and not entry.check(request):
            continue
        # Skip club-required entries when there's no club
        if entry.club_required and not has_club:
            continue
        # A label may be a callable(request) -> str (dynamic label).
        label = entry.label(request) if callable(entry.label) else entry.label
        active = current is not None and current in (entry.url_name, *entry.also_current)
        if entry.club_required:
            url = reverse(entry.url_name, args=[club.slug])
        else:
            url = reverse(entry.url_name)
        link = NavLink(
            label,
            url,
            entry.url_name,
            active,
            entry.icon,
        )
        result[entry.group].append(link)
        if (
            entry.icon
            and entry.shortcut_order is not None
            and entry.group not in ("primary", "account", "gm", "admin")
        ):
            key = entry.shortcut_order
            shortcuts.append((key, link._replace(label=entry.shortcut_label or link.label)))
    result["primary"].extend(link for _, link in sorted(shortcuts, key=lambda t: t[0]))
    return result
