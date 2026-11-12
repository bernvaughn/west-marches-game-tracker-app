from urllib.parse import urlsplit

from django.http import Http404
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..models import Character
from ..selection import own_characters, set_selected_character

# Pages that follow the switch to the new character's same page (U42).
SAME_PAGE = {"characters:detail", "ledger:character_history", "characters:print_items"}
# Pages tied to the old character: land on the new character's sheet.
TO_SHEET = {
    "characters:edit",
    "characters:handover",
    "characters:adjust",
    "characters:consume",
    "characters:transfer",
    "characters:print_item",
}


def _follow(request, target, new):
    try:
        match = resolve(urlsplit(target).path)
    except Resolver404:
        return None
    kwargs = match.kwargs
    if match.view_name not in SAME_PAGE | TO_SHEET:
        return None
    if kwargs.get("club_slug") != request.club.slug:
        return None
    if kwargs.get("pk") not in set(own_characters(request).values_list("pk", flat=True)):
        return None
    name = match.view_name if match.view_name in SAME_PAGE else "characters:detail"
    return reverse(name, kwargs={"club_slug": request.club.slug, "pk": new.pk})


@require_POST
@club_member_required
def select(request, club_slug):
    try:
        pk = int(request.POST.get("character", ""))
    except ValueError:
        raise Http404("No such character.") from None
    character = club_get_object_or_404(request, Character, pk=pk)
    set_selected_character(request, character)
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = None
    if target:
        target = _follow(request, target, character) or target
    return redirect(target or "club_home", **({} if target else {"club_slug": request.club.slug}))
