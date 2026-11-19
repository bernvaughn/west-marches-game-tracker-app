from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.db.models.functions import Lower
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from accounts.mixins import (
    CharacterContextMixin,
    ClubContextMixin,
    ClubScopedMixin,
    PermissionMixin,
)
from accounts.permissions import admin_or_gm_required, club_admin_required, club_member_required
from ledger.models import LedgerEntry, LedgerLine
from quests.services import needed_by_open_quests
from starting_equipment.models import StartingEquipmentTemplate
from starting_equipment.services import apply_starting_equipment

from ..access import can_edit_character, owns_character
from ..character_forms import CharacterForm, HandoverForm
from ..models import Character
from ..player_shop import listed_quantity
from ..sheet import ability_rows, edit_current_values, passive_perception_label


@method_decorator(club_member_required, name="dispatch")
class MineView(ClubContextMixin, CharacterContextMixin, View):
    def get(self, request, club_slug):
        character = self.get_selected_character()
        if character:
            return redirect("characters:detail", club_slug=self.club.slug, pk=character.pk)
        return render(request, "player_characters/characters/mine_empty.html")


@method_decorator(club_member_required, name="dispatch")
class DirectoryView(ClubScopedMixin, PermissionMixin, ClubContextMixin, View):
    def get(self, request, club_slug):
        sees_all = self.is_club_admin(request.user, self.club) or self.is_game_master(
            request.user, self.club
        )
        characters = (
            self.get_club_queryset(Character).select_related("owner__user").order_by(Lower("name"))
        )
        mine = getattr(request.membership, "pk", None)
        rows = []
        for c in characters:
            own = c.owner_id == mine
            url = (
                reverse("characters:detail", args=[self.club.slug, c.pk])
                if sees_all or own
                else None
            )
            rows.append(
                {
                    "character": c,
                    "url": url,
                    "own": own,
                }
            )
        return render(request, "player_characters/characters/directory.html", {"rows": rows})


@method_decorator(admin_or_gm_required, name="dispatch")
class IndexView(ClubScopedMixin, View):
    def get(self, request, club_slug):
        characters = self.get_club_queryset(Character).select_related("owner__user")
        return render(
            request, "player_characters/characters/index.html", {"characters": characters}
        )


@method_decorator(club_member_required, name="dispatch")
class CreateView(ClubScopedMixin, PermissionMixin, ClubContextMixin, View):
    def get(self, request, club_slug):
        can_pick = self.is_club_admin(request.user, self.club) or self.is_game_master(
            request.user, self.club
        )
        initial = {"owner": self.membership} if can_pick and self.membership else {}
        form = CharacterForm(club=self.club, choose_owner=can_pick, initial=initial)
        return render(
            request,
            "player_characters/characters/form.html",
            {"form": form, "title": "New character"},
        )

    def post(self, request, club_slug):
        can_pick = self.is_club_admin(request.user, self.club) or self.is_game_master(
            request.user, self.club
        )
        initial = {"owner": self.membership} if can_pick and self.membership else {}
        form = CharacterForm(request.POST, club=self.club, choose_owner=can_pick, initial=initial)
        if form.is_valid():
            character = form.save(commit=False)
            if not can_pick:
                character.owner = self.membership
            character.save()
            template = StartingEquipmentTemplate.objects.filter(
                club=self.club, is_active=True
            ).first()
            if template:
                entry = apply_starting_equipment(character, template, request.user)
                # Only mark as claimed if equipment was actually granted
                if entry is not None:
                    character.starting_equipment_claimed = True
                    character.save(update_fields=["starting_equipment_claimed"])
            messages.success(request, f"Created {character.name}.")
            url = reverse(
                "characters:detail", kwargs={"club_slug": self.club.slug, "pk": character.pk}
            )
            return redirect(f"{url}?starting_equipment=1")
        return render(
            request,
            "player_characters/characters/form.html",
            {"form": form, "title": "New character"},
        )


@method_decorator(club_member_required, name="dispatch")
class DetailView(ClubScopedMixin, PermissionMixin, CharacterContextMixin, ClubContextMixin, View):
    def get(self, request, club_slug, pk):
        return self._render_detail(request, club_slug, pk)

    def post(self, request, club_slug, pk):
        # Handle POST from "Print sheet" button: update last_printed_at
        character = self.get_club_object_or_404(Character, pk=pk)
        can_view = self.can_view_inventory(request.user, character)
        if not can_view:
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden()
        character.last_printed_at = timezone.now()
        character.save(update_fields=["last_printed_at"])
        return self._render_detail(request, club_slug, pk)

    def _render_detail(self, request, club_slug, pk):
        character = self.get_club_object_or_404(Character, pk=pk)
        can_view = self.can_view_inventory(request.user, character)
        is_owner = owns_character(request.user, character)
        admin = self.is_club_admin(request.user, self.club)
        gm = self.is_game_master(request.user, self.club)
        template = (
            StartingEquipmentTemplate.objects.filter(club=self.club, is_active=True)
            .order_by("name")
            .first()
        )
        ctx = {
            "character": character,
            "characters_url": reverse(
                "characters:index" if admin or gm else "characters:directory",
                args=[self.club.slug],
            ),
            "owner_name": character.owner.user.display_name,
            "can_view": can_view,
            "can_edit": can_view,
            "can_adjust": admin or gm,
            "can_request_points": owns_character(request.user, character) and not (admin or gm),
            "is_owner": owns_character(request.user, character),
            "can_handover": admin,
            "show_starting_animation": request.GET.get("starting_equipment") == "1",
            "can_request_starting_equipment": owns_character(request.user, character)
            or admin
            or gm,
            "can_claim_starting_equipment": bool(
                (is_owner or admin or gm)
                and not character.starting_equipment_claimed
                and template is not None
                and (character.char_class or character.background)
            ),
            "has_magic_options": template is not None and template.magic_options.exists(),
            "active_template": template,
        }
        if can_view:
            char_ctx = self.get_character_context(character)
            ctx["abilities"] = ability_rows(character)
            ctx["passive_perception"] = passive_perception_label(character.perception_bonus)
            ctx["rows"] = char_ctx["inventory_rows"]
            ctx["coins"] = char_ctx["coin_summary"]
            ctx["junk"] = {r.item.pk: r.quantity for r in char_ctx["junk_rows"]}
            ctx["junk_value"] = char_ctx["junk_value"]
            needs = needed_by_open_quests(character) if char_ctx["junk_rows"] else {}
            ctx["quest_needs"] = {pk: needs[pk] for pk in ctx["junk"] if pk in needs}
            if character.shop_open:
                ctx["shop_listed"] = listed_quantity(character)
            ctx["recent_entries"] = (
                LedgerEntry.objects.filter(character=character)
                .select_related("created_by")
                .prefetch_related(
                    Prefetch(
                        "lines",
                        queryset=LedgerLine.objects.select_related("item").order_by("id"),
                    )
                )
                .order_by("-date", "-id")[:5]
            )
            ctx["starting_requests"] = character.starting_requests.select_related(
                "item", "decided_by"
            ).order_by("-created")
        return render(request, "player_characters/characters/detail.html", ctx)


@method_decorator(club_member_required, name="dispatch")
class EditView(ClubScopedMixin, ClubContextMixin, View):
    def get(self, request, club_slug, pk):
        character = self.get_club_object_or_404(Character, pk=pk)
        if not can_edit_character(request.user, character):
            raise PermissionDenied
        form = CharacterForm(instance=character, club=self.club)
        return render(
            request,
            "player_characters/characters/form.html",
            {
                "form": form,
                "title": f"Edit {character.name}",
                "character": character,
                "current": edit_current_values(form),
            },
        )

    def post(self, request, club_slug, pk):
        character = self.get_club_object_or_404(Character, pk=pk)
        if not can_edit_character(request.user, character):
            raise PermissionDenied
        form = CharacterForm(request.POST, instance=character, club=self.club)
        if form.is_valid():
            form.save()
            messages.success(request, f"Saved {character.name}.")
            return redirect("characters:detail", club_slug=self.club.slug, pk=character.pk)
        return render(
            request,
            "player_characters/characters/form.html",
            {
                "form": form,
                "title": f"Edit {character.name}",
                "character": character,
                "current": edit_current_values(form),
            },
        )


@method_decorator(club_admin_required, name="dispatch")
class HandoverView(ClubScopedMixin, ClubContextMixin, View):
    def get(self, request, club_slug, pk):
        character = self.get_club_object_or_404(Character, pk=pk)
        form = HandoverForm(character=character)
        return render(
            request,
            "player_characters/characters/handover.html",
            {"form": form, "character": character},
        )

    def post(self, request, club_slug, pk):
        character = self.get_club_object_or_404(Character, pk=pk)
        form = HandoverForm(request.POST, character=character)
        if form.is_valid():
            new_owner = form.cleaned_data["owner"]
            character.owner = new_owner
            character.save(update_fields=["owner"])
            messages.success(
                request, f"{character.name} now belongs to {new_owner.user.display_name}."
            )
            return redirect("characters:detail", club_slug=self.club.slug, pk=character.pk)
        return render(
            request,
            "player_characters/characters/handover.html",
            {"form": form, "character": character},
        )
