from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import render

from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404, club_queryset
from player_characters.access import require_inventory_access
from player_characters.models import Character

from .models import LedgerEntry, LedgerLine

PAGE_SIZE = 50


@club_member_required
def index(request, club_slug):
    characters = club_queryset(request, Character).select_related("owner__user")
    m = request.membership
    sees_all = request.user.is_superuser or (m and (m.is_club_admin or m.is_game_master))
    if not sees_all:
        characters = characters.filter(owner=m)
    return render(request, "ledger/index.html", {"characters": characters.order_by("name", "id")})


@club_member_required
def character_history(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)
    entries = (
        LedgerEntry.objects.filter(character=character)
        .select_related("created_by", "reverses")
        .prefetch_related(
            Prefetch("lines", queryset=LedgerLine.objects.select_related("item").order_by("id"))
        )
        .order_by("-date", "-id")
    )
    page_obj = Paginator(entries, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "ledger/history.html",
        {"character": character, "page_obj": page_obj, "entries": page_obj.object_list},
    )
