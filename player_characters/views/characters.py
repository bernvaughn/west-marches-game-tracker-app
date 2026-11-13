from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q
from django.db.models.functions import Lower
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.permissions import (
    admin_or_gm_required,
    can_view_inventory,
    club_admin_required,
    club_member_required,
    is_club_admin,
    is_game_master,
)
from accounts.scoping import club_get_object_or_404, club_queryset
from ledger.models import LedgerEntry, LedgerLine
from quests.services import needed_by_open_quests

from ..access import can_edit_character, owns_character
from ..character_forms import CharacterForm, HandoverForm
from ..inventory import coin_summary, inventory_rows
from ..junk import junk_rows, junk_value
from ..models import Character, Trade
from ..player_shop import listed_quantity
from ..selection import selected_character
from ..sheet import ability_rows, passive_perception_label
from ..trade_services import OPEN


@club_member_required
def mine(request, club_slug):
    character = selected_character(request)
    if character:
        return redirect("characters:detail", club_slug=request.club.slug, pk=character.pk)
    return render(request, "player_characters/characters/mine_empty.html")


@club_member_required
def directory(request, club_slug):
    sees_all = is_club_admin(request.user, request.club) or is_game_master(
        request.user, request.club
    )
    characters = (
        club_queryset(request, Character).select_related("owner__user").order_by(Lower("name"))
    )
    sel = selected_character(request)
    by_other = {}
    if sel:
        open_trades = (
            club_queryset(request, Trade)
            .filter(status__in=OPEN)
            .filter(Q(sender=sel) | Q(receiver=sel))
            .order_by("-created")
        )
        for t in open_trades:
            other_id = t.receiver_id if t.sender_id == sel.pk else t.sender_id
            by_other.setdefault(other_id, []).append(t)
    mine = getattr(request.membership, "pk", None)
    rows = []
    for c in characters:
        own = c.owner_id == mine
        url = (
            reverse("characters:detail", args=[request.club.slug, c.pk])
            if sees_all or own
            else None
        )
        propose_url = None
        if sel and not own:
            propose_url = reverse("trades:propose", args=[request.club.slug]) + f"?to={c.pk}"
        rows.append(
            {
                "character": c,
                "url": url,
                "own": own,
                "trades": [] if own else by_other.get(c.pk, []),
                "propose_url": propose_url,
            }
        )
    return render(
        request, "player_characters/characters/directory.html", {"rows": rows, "selected": sel}
    )


@admin_or_gm_required
def index(request, club_slug):
    characters = club_queryset(request, Character).select_related("owner__user")
    return render(request, "player_characters/characters/index.html", {"characters": characters})


@club_member_required
def create(request, club_slug):
    can_pick = is_club_admin(request.user, request.club) or is_game_master(
        request.user, request.club
    )
    initial = {"owner": request.membership} if can_pick and request.membership else {}
    form = CharacterForm(
        request.POST or None, club=request.club, choose_owner=can_pick, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        character = form.save(commit=False)
        if not can_pick:
            character.owner = request.membership
        character.save()
        messages.success(request, f"Created {character.name}.")
        return redirect("characters:detail", club_slug=request.club.slug, pk=character.pk)
    return render(
        request, "player_characters/characters/form.html", {"form": form, "title": "New character"}
    )


@club_member_required
def detail(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    can_view = can_view_inventory(request.user, character)
    admin = is_club_admin(request.user, request.club)
    ctx = {
        "character": character,
        "characters_url": reverse(
            "characters:index"
            if admin or is_game_master(request.user, request.club)
            else "characters:directory",
            args=[request.club.slug],
        ),
        "owner_name": character.owner.user.display_name,
        "can_view": can_view,
        "can_edit": can_view,
        "can_adjust": admin or is_game_master(request.user, request.club),
        "can_handover": admin,
        "can_transfer": owns_character(request.user, character)
        and Character.objects.for_club(request.club).filter(owner=character.owner).count() >= 2,
    }
    if can_view:
        ctx["abilities"] = ability_rows(character)
        ctx["passive_perception"] = passive_perception_label(character.perception_bonus)
        ctx["rows"] = inventory_rows(character)
        ctx["coins"] = coin_summary(character)
        ctx["show_held"] = any(r.held for r in ctx["rows"])
        junk = junk_rows(character)
        ctx["junk"] = {r.item.pk: r.quantity for r in junk}
        ctx["junk_value"] = junk_value(character, junk)
        needs = needed_by_open_quests(character) if junk else {}
        ctx["quest_needs"] = {pk: needs[pk] for pk in ctx["junk"] if pk in needs}
        if character.shop_open:
            ctx["shop_listed"] = listed_quantity(character)
        ctx["recent_entries"] = (
            LedgerEntry.objects.filter(character=character)
            .select_related("created_by")
            .prefetch_related(
                Prefetch("lines", queryset=LedgerLine.objects.select_related("item").order_by("id"))
            )
            .order_by("-date", "-id")[:5]
        )
    return render(request, "player_characters/characters/detail.html", ctx)


@club_member_required
def edit(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    if not can_edit_character(request.user, character):
        raise PermissionDenied
    form = CharacterForm(request.POST or None, instance=character, club=request.club)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {character.name}.")
        return redirect("characters:detail", club_slug=request.club.slug, pk=character.pk)
    return render(
        request,
        "player_characters/characters/form.html",
        {"form": form, "title": f"Edit {character.name}", "character": character},
    )


@club_admin_required
def handover(request, club_slug, pk):
    character = club_get_object_or_404(request, Character, pk=pk)
    form = HandoverForm(request.POST or None, character=character)
    if request.method == "POST" and form.is_valid():
        new_owner = form.cleaned_data["owner"]
        character.owner = new_owner
        character.save(update_fields=["owner"])
        messages.success(request, f"{character.name} now belongs to {new_owner.user.display_name}.")
        return redirect("characters:detail", club_slug=request.club.slug, pk=character.pk)
    return render(
        request,
        "player_characters/characters/handover.html",
        {"form": form, "character": character},
    )
