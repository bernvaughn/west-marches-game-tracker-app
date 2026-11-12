from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect

from accounts.htmx import is_htmx, render_modal_or_page
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404
from items.models import Item
from ledger.services import item_quantities

from ..access import require_inventory_access
from ..forms_junk import JunkForm
from ..junk import JunkError, set_junk
from ..models import Character, JunkMark


@club_member_required
def junk(request, club_slug, pk, item_pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    item = club_get_object_or_404(request, Item, pk=item_pk)
    require_inventory_access(request.user, character)
    owned = item_quantities(character).get(item.pk, 0)
    if owned < 1:
        raise Http404("The character owns none of this item.")
    sheet = redirect("characters:detail", club_slug=club_slug, pk=character.pk)
    if request.method == "POST":
        form = JunkForm(request.POST, owned=owned)
        if form.is_valid():
            try:
                set_junk(character, item, form.cleaned_data["quantity"], request.user)
            except JunkError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"Saved junk marks for {character.name}.")
                if is_htmx(request):
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = sheet.url
                    return response
                return sheet
    else:
        mark = JunkMark.objects.filter(character=character, item=item).first()
        form = JunkForm(initial={"quantity": min(mark.quantity, owned) if mark else 0}, owned=owned)
    return render_modal_or_page(
        request,
        "player_characters/characters/_junk_modal.html",
        "player_characters/characters/junk.html",
        {"character": character, "item": item, "owned": owned, "form": form},
    )
