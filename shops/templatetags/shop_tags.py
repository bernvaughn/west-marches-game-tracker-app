"""Template tags for shop-related UI components."""

from django import template
from django.utils import timezone

from shops.services import open_shops

register = template.Library()


@register.inclusion_tag("components/_shop_switcher.html")
def shop_switcher(club):
    """Render a dropdown of the club's open shops (excludes closed shops)."""
    today = timezone.localdate()
    return {"club": club, "open_shops": open_shops(club, today)}
