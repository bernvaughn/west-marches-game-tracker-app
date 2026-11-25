from django import template
from django.core.paginator import Paginator
from django.urls import NoReverseMatch, reverse

from downtime import services
from downtime.ev import entry_value_cp
from downtime.models import DowntimePointEntry
from ledger.coins import format_coins
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


@register.filter
def expected_value_total(formset):
    """
    Compute the expected value total for a downtime entry formset.

    Takes the entry formset, iterates over each form's instance,
    computes expected_value_cp over the entries, returns formatted coins
    or empty string when zero.
    """
    if not hasattr(formset, "forms"):
        return ""

    entries = []
    for form in formset.forms:
        # Skip deleted forms
        if form.is_bound and form.cleaned_data and form.cleaned_data.get("DELETE"):
            continue

        # Use instance for existing entries, cleaned_data for new/bound forms
        if form.instance and form.instance.pk:
            entries.append(form.instance)
        elif form.is_bound and form.cleaned_data and form.cleaned_data.get("label"):
            # For unsaved forms in a POST, create a temporary entry-like object
            from types import SimpleNamespace

            weight = form.cleaned_data.get("weight", 0)
            coins = form.cleaned_data.get("coins", 0)
            items = []

            # Add nested items if available
            if hasattr(form, "nested") and form.nested:
                for n in form.nested.forms:
                    if n.is_bound and n.cleaned_data and n.cleaned_data.get("DELETE"):
                        continue
                    if n.instance and n.instance.pk:
                        items.append(n.instance)
                    elif n.is_bound and n.cleaned_data and n.cleaned_data.get("item"):
                        # Create a simple object with item and quantity
                        item_obj = n.cleaned_data["item"]
                        qty = n.cleaned_data.get("quantity", 1)
                        items.append(SimpleNamespace(item=item_obj, quantity=qty))

            entry = SimpleNamespace(
                weight=weight,
                coins=coins,
                items=items,
            )
            entries.append(entry)

    if not entries:
        return ""

    ev_cp = 0
    total_weight = sum(e.weight for e in entries if e.weight)
    if total_weight > 0:
        weighted_sum = sum(e.weight * entry_value_cp(e) for e in entries)
        ev_cp = weighted_sum // total_weight

    if ev_cp == 0:
        return ""
    return format_coins(ev_cp)


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
