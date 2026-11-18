"""Template tags for shop-related UI components."""

from django import template
from django.utils import timezone

from shops.services import open_shops, ordered_shops

register = template.Library()


@register.inclusion_tag("components/_shop_switcher.html")
def shop_switcher(club, current=None):
    """Render a dropdown of the club's open shops (excludes closed shops).

    `current` marks the active shop with aria-current="page".
    """
    today = timezone.localdate()
    return {"club": club, "open_shops": ordered_shops(open_shops(club, today)), "current": current}
