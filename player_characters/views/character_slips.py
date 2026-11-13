from django.db.models.functions import Lower
from django.shortcuts import render

from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_queryset

from ..forms_slips import SlipsForm
from ..models import Character
from ..sheet import DASH, passive_perception

SLIPS_PER_SHEET = 12
T = "player_characters/characters/"


def slip_queryset(request):
    qs = club_queryset(request, Character).select_related("owner__user").order_by(Lower("name"))
    club = getattr(request, "club", None)
    if is_club_admin(request.user, club) or is_game_master(request.user, club):
        return qs
    membership = getattr(request, "membership", None)
    if membership is None:
        return qs.none()
    return qs.filter(owner=membership)


def _slip(c):
    passive = passive_perception(c.perception_bonus)
    return {
        "player": c.owner.user.display_name or c.owner.user.email,
        "name": c.name,
        "pronouns": c.pronouns or DASH,
        "passive": DASH if passive is None else passive,
        "level": c.level if c.level is not None else DASH,
        "char_class": c.char_class or DASH,
        "species": c.species or DASH,
    }


@club_member_required
def slips(request, club_slug):
    qs = slip_queryset(request)
    return render(request, T + "slips.html", {"form": SlipsForm(queryset=qs), "characters": qs})


@club_member_required
def slips_print(request, club_slug):
    qs = slip_queryset(request)
    form = SlipsForm(request.GET, queryset=qs)
    if not form.is_valid():
        return render(request, T + "slips.html", {"form": form, "characters": qs})
    chosen = sorted(form.cleaned_data["characters"], key=lambda c: c.name.lower())
    items = [_slip(c) for c in chosen]
    sheets = [items[i : i + SLIPS_PER_SHEET] for i in range(0, len(items), SLIPS_PER_SHEET)]
    return render(request, T + "slips_print.html", {"sheets": sheets})
