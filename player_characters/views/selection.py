from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..models import Character
from ..selection import set_selected_character


@require_POST
@club_member_required
def select(request, club_slug):
    try:
        pk = int(request.POST.get("character", ""))
    except ValueError:
        raise Http404("No such character.") from None
    character = club_get_object_or_404(request, Character, pk=pk)
    set_selected_character(request, character)
    messages.success(request, f"Acting as {character.name}.")
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = None
    return redirect(target or "club_home", **({} if target else {"club_slug": request.club.slug}))
