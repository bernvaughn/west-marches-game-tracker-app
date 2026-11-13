from django import template
from django.core.paginator import Paginator
from django.urls import NoReverseMatch, reverse

from downtime import services
from downtime.models import DowntimePointEntry
from player_characters.models import Character

register = template.Library()


@register.filter
def lookup(mapping, key):
    """Look up a (possibly model-choice) value in a dict keyed by pk."""
    return mapping.get(getattr(key, "value", key), 0)


@register.simple_tag
def downtime_balance(character):
    return services.balance(character)


@register.simple_tag
def downtime_play_url(club):
    try:
        return reverse("downtime:play", args=[club.slug])
    except NoReverseMatch:
        return ""


@register.inclusion_tag("downtime/_points_section.html", takes_context=True)
def downtime_points_section(context, character=None):
    request = context["request"]
    club = request.club
    entries = DowntimePointEntry.objects.for_club(club).select_related("character", "created_by")
    if character is not None:
        entries = entries.filter(character=character)
    else:
        pk = request.GET.get("character", "")
        if pk.isdigit() and Character.objects.for_club(club).filter(pk=pk).exists():
            entries = entries.filter(character_id=pk)
    kind = request.GET.get("points_kind", "")
    if kind not in DowntimePointEntry.Kind.values:
        kind = ""
    if kind:
        entries = entries.filter(kind=kind)
    page = Paginator(entries, 50).get_page(request.GET.get("points_page"))
    hidden = [
        (k, v)
        for k, values in request.GET.lists()
        if k not in ("points_kind", "points_page")
        for v in values
    ]
    return {
        "request": request,
        "page_obj": page,
        "show_character": character is None,
        "kind": kind,
        "kinds": DowntimePointEntry.Kind.choices,
        "hidden": hidden,
    }
