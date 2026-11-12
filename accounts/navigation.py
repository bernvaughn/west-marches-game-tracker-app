"""Registry of top-bar navigation entries (U29).

Each app registers entries from `apps.py` `ready()`. `check(request) -> bool`;
`None` means always shown. All club pages take the club slug.
"""

from typing import NamedTuple

from django.urls import reverse

GROUPS = ("primary", "more", "gm", "admin")


class NavEntry(NamedTuple):
    group: str
    label: str
    url_name: str
    check: object
    order: int


class NavLink(NamedTuple):
    label: str
    url: str
    url_name: str
    active: bool


_entries = []


def register(group, label, url_name, check=None, order=100):
    if group not in GROUPS:
        raise ValueError(f"Unknown navigation group: {group!r}")
    for existing in _entries:
        if existing.group == group and existing.url_name == url_name:
            return existing
    entry = NavEntry(group, label, url_name, check, order)
    _entries.append(entry)
    return entry


def entries_for(request):
    result = {group: [] for group in GROUPS}
    user = getattr(request, "user", None)
    club = getattr(request, "club", None)
    if club is None or user is None or not user.is_authenticated:
        return result
    match = getattr(request, "resolver_match", None)
    current = match.url_name if match else None
    for entry in sorted(_entries, key=lambda e: (e.order, e.label)):
        if entry.check is not None and not entry.check(request):
            continue
        result[entry.group].append(
            NavLink(
                entry.label,
                reverse(entry.url_name, args=[club.slug]),
                entry.url_name,
                entry.url_name == current,
            )
        )
    return result
