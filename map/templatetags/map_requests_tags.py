from django import template

from ..models import MapRequest
from ..visibility import is_map_editor

register = template.Library()


@register.simple_tag(takes_context=True)
def open_map_request_count(context):
    club = context.get("club")
    user = context.get("user")
    if club is None or user is None or not getattr(user, "is_authenticated", False):
        return None
    if not is_map_editor(user, club):
        return None
    return MapRequest.objects.for_club(club).filter(status=MapRequest.Status.REQUESTED).count()
