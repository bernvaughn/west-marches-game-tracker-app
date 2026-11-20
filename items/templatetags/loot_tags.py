"""Template tags for rendering loot previews."""

from django import template

from accounts.permissions import can_see_gm_details
from items.containers import loot_preview as _loot_preview

register = template.Library()


@register.simple_tag(takes_context=True)
def loot_preview(context, item):
    """Return loot preview rows for a container item.

    Returns an empty list for non-container items or when item is None.
    The tag reads request.user and request.club from context to determine
    whether unknown items should be masked.
    """
    if not item or not item.is_container:
        return []

    request = context.get("request")
    if not request:
        return []

    viewer_can_see_unknown = can_see_gm_details(request.user, request.club)
    return _loot_preview(item, viewer_can_see_unknown)
