from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from accounts.htmx import is_htmx, render_modal_or_page, set_hx_headers
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from items.opening import OpenError, open_container, opening_view_model
from player_characters.access import require_inventory_access
from player_characters.models import Character


@club_member_required
@require_POST
def open_container_view(request, club_slug, pk, item_pk):
    """Open a container item from a character's inventory. POST only.

    The character owner, a GM or a club admin may open. Other players get
    403; members of other clubs get 404 via club scoping; anonymous users
    are redirected to login by ``club_member_required``.
    """

    character = club_get_object_or_404(request, Character, pk=pk)
    container = club_get_object_or_404(request, Item, pk=item_pk)
    if not container.is_container:
        raise Http404("That item is not a container.")
    require_inventory_access(request.user, character)

    try:
        opening = open_container(character, container, request.user)
    except OpenError as exc:
        if is_htmx(request):
            return render_modal_or_page(
                request,
                "player_characters/characters/_open_result_modal.html",
                "player_characters/characters/open_result.html",
                {
                    "character": character,
                    "container": container,
                    "error": str(exc),
                },
            )
        messages.error(request, str(exc))
        return redirect("characters:detail", club_slug=club_slug, pk=character.pk)

    rows = opening_view_model(opening)
    ctx = {
        "character": character,
        "container": container,
        "opening": opening,
        "rows": rows,
    }
    response = render_modal_or_page(
        request,
        "player_characters/characters/_open_result_modal.html",
        "player_characters/characters/open_result.html",
        ctx,
    )
    return set_hx_headers(response, trigger="containerOpened")
