"""Registry of "things waiting for you" shown in the navbar (U26 adds providers).

A provider is a callable `provider(request)` returning `(label, count, url)` or None.
"""

from typing import NamedTuple


class Approval(NamedTuple):
    label: str
    count: int
    url: str


_providers = []


def register(provider):
    if provider not in _providers:
        _providers.append(provider)
    return provider


def pending_approvals(request):
    user = getattr(request, "user", None)
    if getattr(request, "club", None) is None or user is None or not user.is_authenticated:
        return []
    items = []
    for provider in list(_providers):
        result = provider(request)
        if result is None:
            continue
        item = Approval(*result)
        if item.count > 0:
            items.append(item)
    return items


def context_processor(request):
    items = pending_approvals(request)
    return {"approvals": items, "approvals_total": sum(i.count for i in items)}
