from django.db.models.functions import Lower
from django.shortcuts import render
from django.urls import reverse

from accounts.permissions import club_member_required, is_club_admin, is_game_master
from accounts.scoping import club_queryset

from ..forms_slips import SlipsForm
from ..models import Character
from ..sheet import ability_rows, passive_perception

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


def _pills(pairs):
    """Label/value pills, with blank values left out."""
    return [{"label": k, "value": v} for k, v in pairs if v is not None and v != ""]


def _slip(c):
    return {
        "player": c.owner.user.display_name or c.owner.user.email,
        "name": c.name,
        "pronouns": c.pronouns or "",
        "pills_top": _pills([("Species", c.species), ("Class", c.char_class), ("Level", c.level)]),
        "pills_bottom": _pills(
            [
                ("AC", c.armor_class),
                ("Passive Perc.", passive_perception(c.perception_bonus)),
                ("Max HP", c.max_hp),
            ]
        ),
        "abilities": ability_rows(c),
    }


def _back_link(request, qs, club_slug):
    """Back to the sheet when sent from one (and the id is visible to the user), else to slips."""
    raw = request.GET.get("character", "")
    if request.GET.get("from") == "sheet" and raw.isdigit() and qs.filter(pk=int(raw)).exists():
        return reverse("characters:detail", args=[club_slug, int(raw)]), "Back to sheet"
    return reverse("characters:slips", args=[club_slug]), "Back to slips"


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
    back_url, back_label = _back_link(request, qs, club_slug)
    return render(
        request,
        T + "slips_print.html",
        {"sheets": sheets, "back_url": back_url, "back_label": back_label},
    )
