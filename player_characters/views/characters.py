from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Case, IntegerField, Prefetch, When
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
from accounts.permissions import (
    admin_or_gm_required,
    club_admin_required,
    club_member_required,
    is_club_admin,
)
from ledger.models import LedgerEntry, LedgerLine
from quests.services import needed_by_open_quests
from starting_equipment.models import StartingEquipmentTemplate
from starting_equipment.services import (
    claim_starting_equipment,
    explain_starting_equipment,
    get_choice_groups,
)

from ..access import can_edit_character, owns_character
from ..character_forms import CharacterForm, HandoverForm
from ..junk import get_junk_summary
from ..models import Character
from ..notes import item_notes
from ..player_shop import listed_quantity
from ..selection import selected_character
from ..sheet import (
    ability_rows,
    edit_current_values,
    passive_perception_label,
    xp_progress,
)


@method_decorator(club_member_required, name="dispatch")
class MineView(ClubContextMixin, CharacterContextMixin, View):
    def get(self, request, club_slug):
        character = self.get_selected_character()
        if character:
            return redirect("characters:detail", club_slug=self.club.slug, pk=character.pk)
        return render(request, "player_characters/characters/mine_empty.html")


def _life_filter(request, is_admin):
    """Return 'living', 'dead' or 'all' from ?status=. Only a club admin may filter."""
    if not is_admin:
        return "all"
    status = request.GET.get("status", "all")
    return status if status in ("living", "dead", "all") else "all"


def _dead_last_ordering():
    """Order characters so dead ones sort after living ones, then by name."""
    return (
        Case(When(died_on__isnull=False, then=1), default=0, output_field=IntegerField()),
        Lower("name"),
    )


@method_decorator(club_member_required, name="dispatch")
class DirectoryView(ClubScopedMixin, PermissionMixin, ClubContextMixin, View):
    def get(self, request, club_slug):
        admin = self.is_club_admin(request.user, self.club)
        sees_all = admin or self.is_game_master(request.user, self.club)
        status = _life_filter(request, admin)
        characters = self.get_club_queryset(Character).not_archived().select_related("owner__user")
        if status == "living":
            characters = characters.living()
        elif status == "dead":
            characters = characters.dead()
        characters = characters.order_by(*_dead_last_ordering())
        if status == "dead":
            empty_text = "No dead characters."
        elif status == "living":
            empty_text = "No living characters."
        else:
            empty_text = "No characters yet."
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
        return render(
            request,
            "player_characters/characters/directory.html",
            {
                "rows": rows,
                "status": status,
                "can_filter": admin,
                "archive_secondary": [
                    {
                        "url": reverse("characters:archived", args=[self.club.slug]),
                        "label": "Archived characters",
                    }
                ],
                "empty_text": empty_text,
            },
        )


@method_decorator(admin_or_gm_required, name="dispatch")
class IndexView(ClubScopedMixin, View):
    def get(self, request, club_slug):
        admin = is_club_admin(request.user, request.club)
        status = _life_filter(request, admin)
        characters = self.get_club_queryset(Character).not_archived().select_related("owner__user")
        if status == "living":
            characters = characters.living()
        elif status == "dead":
            characters = characters.dead()
        characters = characters.order_by(*_dead_last_ordering())
        if status == "dead":
            empty_text = "No dead characters."
        elif status == "living":
            empty_text = "No living characters."
        else:
            empty_text = "No characters yet."
        return render(
            request,
            "player_characters/characters/index.html",
            {
                "characters": characters,
                "status": status,
                "can_filter": admin,
                "archive_secondary": [
                    {
                        "url": reverse("characters:archived", args=[request.club.slug]),
                        "label": "Archived characters",
                    }
                ],
                "empty_text": empty_text,
            },
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
            groups = get_choice_groups(character, template)
            if groups:
                # Choice groups exist: send the player to pick before granting gear.
                messages.success(request, f"Created {character.name}.")
                return redirect(
                    "starting_equipment:choices",
                    club_slug=self.club.slug,
                    character_pk=character.pk,
                )
            result = claim_starting_equipment(character, template, request.user)
            messages.success(request, f"Created {character.name}.")
            for reason in result.reasons:
                messages.warning(request, reason.message)
            if result.entry is not None:
                return redirect(
                    "characters:starting_reveal",
                    club_slug=self.club.slug,
                    pk=character.pk,
                )
            return redirect("characters:detail", club_slug=self.club.slug, pk=character.pk)
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
        selected = selected_character(request)
        admin = self.is_club_admin(request.user, self.club)
        gm = self.is_game_master(request.user, self.club)
        template = (
            StartingEquipmentTemplate.objects.filter(club=self.club, is_active=True)
            .order_by("name")
            .first()
        )
        choice_groups = get_choice_groups(character, template)
        can_claim_starting_equipment = bool(
            (is_owner or admin or gm)
            and not character.starting_equipment_claimed
            and template is not None
            and (character.char_class or character.background)
        )
        starting_choices_url = None
        if can_claim_starting_equipment and choice_groups:
            starting_choices_url = reverse(
                "starting_equipment:choices",
                kwargs={"club_slug": self.club.slug, "character_pk": character.pk},
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
            "can_sell_junk": is_owner and selected is not None and character.pk == selected.pk,
            "can_handover": admin,
            "show_starting_animation": request.GET.get("starting_equipment") == "1",
            "can_request_starting_equipment": owns_character(request.user, character)
            or admin
            or gm,
            "can_claim_starting_equipment": can_claim_starting_equipment,
            "starting_choices_url": starting_choices_url,
            "has_magic_options": template is not None and template.magic_options.exists(),
            "active_template": template,
        }
        if can_view and template is not None:
            ctx["starting_equipment_reasons"] = [
                reason
                for reason in explain_starting_equipment(character, template)
                if reason.code != "no_template"
            ]
        if can_view:
            char_ctx = self.get_character_context(character)
            junk_summary = get_junk_summary(character)
            ctx["abilities"] = ability_rows(character)
            ctx["passive_perception"] = passive_perception_label(character.perception_bonus)
            ctx["xp_progress"] = xp_progress(character)
            ctx["rows"] = char_ctx["inventory_rows"]
            ctx["coins"] = char_ctx["coin_summary"]
            ctx["junk"] = {r.item.pk: r.quantity for r in junk_summary["rows"]}
            ctx["junk_value"] = junk_summary["value"]
            raw_notes = item_notes(character)
            notes = {}
            for item_pk, text in raw_notes.items():
                first = text.split("\n")[0] if text else ""
                notes[item_pk] = {
                    "text": text,
                    "first": first[:120],
                    "icon": "sticky-fill" if text else "sticky",
                    "title": first[:120] if text else "Add your own note about this item.",
                    "aria": "Edit note" if text else "Add note",
                }
            ctx["notes"] = notes
            needs = needed_by_open_quests(character) if junk_summary["rows"] else {}
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
