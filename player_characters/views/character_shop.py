from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404

from ..access import require_inventory_access
from ..models import Character


@require_POST
@club_member_required
def shop_toggle(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)
    character.shop_open = request.POST.get("shop_open") == "on"
    character.save(update_fields=["shop_open"])
    messages.success(
        request,
        f"{character.name}'s shop is {'open' if character.shop_open else 'closed'}.",
    )
    sheet = redirect("characters:detail", club_slug=club_slug, pk=character.pk)
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = sheet.url
        return response
    return sheet
