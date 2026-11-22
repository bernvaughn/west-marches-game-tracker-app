from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.apps import is_gm_or_admin
from accounts.permissions import club_member_required
from accounts.scoping import club_get_object_or_404, club_queryset
from player_characters.access import require_inventory_access
from player_characters.models import Character, CharacterStatusChange
from player_characters.selection import selected_character

from .filters import LedgerFilterForm
from .models import LedgerEntry, LedgerLine

PAGE_SIZE = 50
STATUS_PAGE_SIZE = 50


def can_use_club_ledger(request):
    return is_gm_or_admin(request)


def _status_changes_for(request, character=None, form=None):
    """Return a queryset of CharacterStatusChange rows for the club, optionally filtered.

    Filters that make sense: character, player (character__owner),
    date_from/date_to on `date`, recorded_by (by__user).
    Uses form._values() for cleaned, non-empty filter values.
    """
    qs = (
        CharacterStatusChange.objects.for_club(request.club)
        .select_related("character__owner__user", "by__user")
        .order_by("-at", "-id")
    )
    if character is not None:
        qs = qs.filter(character=character)
    if form is not None and form.is_valid():
        v = form._values()
        if "character" in v:
            qs = qs.filter(character=v["character"])
        if "player" in v:
            qs = qs.filter(character__owner=v["player"])
        if "date_from" in v:
            qs = qs.filter(date__gte=v["date_from"])
        if "date_to" in v:
            qs = qs.filter(date__lte=v["date_to"])
        if "recorded_by" in v:
            qs = qs.filter(by__user=v["recorded_by"])
    return qs


def _should_show_status_changes(form):
    """Return True if the status changes section should be shown.

    Ledger-only filters (kind, item, downtime) hide the section.
    """
    if form is None or not form.is_valid():
        return True
    v = form._values()
    return not any(k in v for k in ("kind", "item", "downtime"))


@club_member_required
def index(request, club_slug):
    if not can_use_club_ledger(request):
        character = selected_character(request)
        if character is None:
            return render(request, "ledger/index.html", {"no_character": True})
        return redirect("ledger:character_history", club_slug=request.club.slug, pk=character.pk)
    form = LedgerFilterForm(request.GET, request.club)
    qs = (
        form.filter(club_queryset(request, LedgerEntry))
        .select_related(
            "character__owner__user",
            "created_by",
            "shop",
            "agent_batch",
            "source_message",
            "reverses",
            "downtime_result__action",
            "downtime_result__entry",
        )
        .prefetch_related(
            Prefetch("lines", queryset=LedgerLine.objects.select_related("item").order_by("id"))
        )
        .order_by("-date", "-id")
    )
    page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))

    # Status changes section (separate pagination)
    show_status = _should_show_status_changes(form)
    status_changes = None
    if show_status:
        sc_qs = _status_changes_for(request, form=form)
        status_page_obj = Paginator(sc_qs, STATUS_PAGE_SIZE).get_page(request.GET.get("status_page"))
        status_changes = status_page_obj

    m = request.membership
    return render(
        request,
        "ledger/index.html",
        {
            "form": form,
            "page_obj": page_obj,
            "entries": page_obj.object_list,
            "filter_qs": form.querystring(),
            "is_gm": request.user.is_superuser or bool(m and m.is_game_master),
            "is_admin": request.user.is_superuser or bool(m and m.is_club_admin),
            "status_changes": status_changes,
        },
    )


@club_member_required
def character_history(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    require_inventory_access(request.user, character)
    entries = (
        LedgerEntry.objects.filter(character=character)
        .select_related(
            "created_by", "reverses", "downtime_result__action", "downtime_result__entry"
        )
        .prefetch_related(
            Prefetch("lines", queryset=LedgerLine.objects.select_related("item").order_by("id"))
        )
        .order_by("-date", "-id")
    )
    page_obj = Paginator(entries, PAGE_SIZE).get_page(request.GET.get("page"))

    # Status changes for this character (separate pagination)
    sc_qs = _status_changes_for(request, character=character)
    status_page_obj = Paginator(sc_qs, STATUS_PAGE_SIZE).get_page(request.GET.get("status_page"))

    back_url = reverse("characters:detail", args=[request.club.slug, character.pk])
    back_label = "Back to sheet"
    if request.GET.get("from") == "ledger" and can_use_club_ledger(request):
        qs = LedgerFilterForm(request.GET, request.club).querystring()
        page = request.GET.get("ledger_page", "")
        if page.isdigit():
            qs = (qs + "&" if qs else "") + f"page={page}"
        back_url = reverse("ledger:index", args=[request.club.slug]) + (f"?{qs}" if qs else "")
        back_label = "Back to club ledger"
    return render(
        request,
        "ledger/history.html",
        {
            "character": character,
            "page_obj": page_obj,
            "entries": page_obj.object_list,
            "back_url": back_url,
            "back_label": back_label,
            "status_changes": status_page_obj,
        },
    )
