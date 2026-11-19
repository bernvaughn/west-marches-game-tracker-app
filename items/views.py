from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.http import require_POST

from accounts.htmx import render_modal_or_page
from accounts.mixins import ClubContextMixin, ClubScopedMixin, PermissionMixin
from accounts.permissions import admin_or_gm_required, club_admin_required, club_member_required
from ledger.coins import CP_PER_GP, CP_PER_PP, CP_PER_SP
from player_characters.item_cards import CARD_CAP, CARDS_PER_SHEET, build_cards, chunk, too_many

from .availability import available_item_ids
from .availability import where_to_buy as find_where_to_buy
from .containers import validate_container_config
from .forms import ItemForm, SlotFormSet
from .magic_types import NONE_LABEL, MagicType
from .models import Item
from .rarity import Rarity
from .references import reference_items
from .services import delete_or_retire
from .usage import ownership_counts


@method_decorator(club_member_required, name="dispatch")
class IndexView(ClubScopedMixin, PermissionMixin, View):
    def get(self, request, club_slug):
        is_admin = self.is_club_admin(request.user, request.club)
        is_gm = self.is_game_master(request.user, request.club)
        show_retired = is_admin and request.GET.get("retired") == "1"
        items = self.get_club_queryset(Item)
        if not show_retired:
            items = items.filter(retired=False)
        magic_type = request.GET.get("magic_type", "")
        if magic_type == "none":
            items = items.filter(magic_type="")
        elif magic_type in MagicType.values:
            items = items.filter(magic_type=magic_type)
        else:
            magic_type = ""
        items = list(items)
        for_sale = available_item_ids(request.club, timezone.localdate())
        show_counts = is_admin or is_gm
        counts = ownership_counts(request.club) if show_counts else {}
        for i in items:
            i.for_sale = i.pk in for_sale
            own = counts.get(i.pk)
            i.owner_count = own.characters if own else 0
            i.held_total = own.held if own else 0
        return render(
            request,
            "items/index.html",
            {
                "items": items,
                "is_admin": is_admin,
                "is_game_master": is_gm,
                "show_retired": show_retired,
                "show_counts": show_counts,
                "magic_type": magic_type,
                "magic_types": [("none", NONE_LABEL), *MagicType.choices],
                "retired_qs": f"&magic_type={magic_type}" if magic_type else "",
            },
        )


@method_decorator(club_member_required, name="dispatch")
class WhereToBuyView(ClubScopedMixin, PermissionMixin, View):
    def get(self, request, club_slug, pk):
        item = self.get_club_object_or_404(Item, pk=pk)
        if item.retired and not self.is_club_admin(request.user, request.club):
            raise Http404
        offers = find_where_to_buy(request.club, item, timezone.localdate(), request.user)
        return render_modal_or_page(
            request,
            "items/_where_to_buy_modal.html",
            "items/where_to_buy.html",
            {"item": item, "offers": offers},
        )


@method_decorator(club_member_required, name="dispatch")
class DetailView(ClubScopedMixin, PermissionMixin, View):
    def get(self, request, club_slug, pk):
        item = self.get_club_object_or_404(Item, pk=pk)
        is_admin = self.is_club_admin(request.user, request.club)
        if item.retired and not is_admin:
            raise Http404
        return render(request, "items/detail.html", {"item": item, "is_admin": is_admin})


@method_decorator(club_member_required, name="dispatch")
class DetailsModalView(ClubScopedMixin, PermissionMixin, View):
    def get(self, request, club_slug, pk):
        item = self.get_club_object_or_404(Item, pk=pk)
        is_admin = self.is_club_admin(request.user, request.club)
        if item.retired and not is_admin:
            raise Http404
        return render_modal_or_page(
            request,
            "items/_details_modal.html",
            "items/detail.html",
            {"item": item, "is_admin": is_admin},
        )


def _form_view(request, instance):
    return _item_form_view(request, instance, with_container=True)


def _create_form_view(request, instance):
    """Form view for create modal - no container config."""
    return _item_form_view(request, instance, with_container=False)


def _item_form_view(request, instance, with_container):
    """Shared form view for create/edit with optional container config."""
    form = ItemForm(request.POST or None, instance=instance, club=request.club)

    # Build container formsets only for edit view with existing item that IS a container
    slot_formset = None
    container_errors = None

    if request.method == "POST":
        # Handle add/remove row buttons
        if "add_slot" in request.POST:
            # Need slot_formset for re-rendering
            if slot_formset is None and with_container and instance.pk:
                slot_formset = SlotFormSet(
                    None,
                    instance=instance,
                    prefix="slots",
                    club=request.club,
                    container=instance,
                )
            return _handle_add_slot(request, instance, form, slot_formset)
        if "add_option" in request.POST:
            if slot_formset is None and with_container and instance.pk:
                slot_formset = SlotFormSet(
                    None,
                    instance=instance,
                    prefix="slots",
                    club=request.club,
                    container=instance,
                )
            return _handle_add_option(request, instance, form, slot_formset)

        # Handle actual save
        is_container = request.POST.get("is_container") == "on"

        # For container save or if item is already a container, build formset with POST data
        if (is_container or instance.is_container) and with_container and instance.pk:
            slot_formset = SlotFormSet(
                request.POST,
                instance=instance,
                prefix="slots",
                club=request.club,
                container=instance,
            )
    else:
        # GET request - show formset for admins on edit page (with_container=True)
        # Create empty formset for non-containers so the toggle is visible
        if with_container and instance.pk:
            slot_formset = SlotFormSet(
                None,
                instance=instance,
                prefix="slots",
                club=request.club,
                container=instance,
            )

    # Validate formset only if it exists and we're saving a container
    if request.method == "POST":
        is_container = request.POST.get("is_container") == "on"
        if is_container and slot_formset is not None:
            # First validate nested option formsets manually
            opts_valid_all = True
            for slot_form in slot_formset.forms:
                if slot_formset.can_delete and slot_formset._should_delete_form(slot_form):
                    continue
                opts = getattr(slot_form, "options", None)
                if opts is not None:
                    # Manually validate each option form
                    for opt_form in opts.forms:
                        if opts.can_delete and opts._should_delete_form(opt_form):
                            continue
                        if not opt_form.is_valid():
                            opts_valid_all = False
                            break
                    if not opts_valid_all:
                        break

            # Then validate slot formset (its clean method uses validated option forms)
            slot_valid = slot_formset.is_valid() and opts_valid_all
        else:
            slot_valid = True
    else:
        slot_valid = True

    if form.is_valid() and slot_valid:
        item = form.save()

        if is_container and slot_formset is not None:
            # Save container config inside atomic transaction
            try:
                with transaction.atomic():
                    slot_formset.instance = item
                    slot_formset.save()
                    # Save nested option formsets
                    for slot_form in slot_formset.forms:
                        if slot_formset.can_delete and slot_formset._should_delete_form(slot_form):
                            continue
                        if not slot_form.cleaned_data:
                            continue
                        opts = getattr(slot_form, "options", None)
                        if opts is not None:
                            opts.instance = slot_form.instance
                            opts.save()
                    # Validate container config after save (reads DB)
                    if is_container:
                        validate_container_config(item)
            except ValidationError as e:
                # Rollback happened, rebuild formsets from POST
                messages.error(request, "; ".join(e.messages))
                container_errors = e.messages
                slot_formset = SlotFormSet(
                    request.POST,
                    instance=item,
                    prefix="slots",
                    club=request.club,
                    container=item,
                )
                return render(
                    request,
                    "items/form.html",
                    {
                        "form": form,
                        "item": item,
                        "slot_formset": slot_formset,
                        "container_errors": container_errors,
                    },
                )
        else:
            # Toggle off - don't process formsets, existing slots stay inert
            pass

        messages.success(request, f"Saved {item.name}.")
        return redirect("items:detail", club_slug=request.club.slug, pk=item.pk)

    return render(
        request,
        "items/form.html",
        {
            "form": form,
            "item": instance,
            "slot_formset": slot_formset,
            "container_errors": container_errors,
        },
    )


def _handle_add_slot(request, instance, form, slot_formset):
    """Handle 'add slot' button - bump TOTAL_FORMS and re-render."""
    post = request.POST.copy()
    prefix = "slots"
    total = int(post.get(f"{prefix}-TOTAL_FORMS", 0))
    post[f"{prefix}-TOTAL_FORMS"] = total + 1
    # Rebuild formset with incremented count
    slot_formset = SlotFormSet(
        post,
        instance=instance,
        prefix=prefix,
        club=request.club,
        container=instance,
    )
    return render(
        request,
        "items/form.html",
        {
            "form": form,
            "item": instance,
            "slot_formset": slot_formset,
        },
    )


def _handle_add_option(request, instance, form, slot_formset):
    """Handle 'add option' button - bump TOTAL_FORMS for a specific slot."""
    # The button value is the slot index
    slot_index = request.POST.get("add_option")
    if slot_index is None:
        return render(
            request,
            "items/form.html",
            {
                "form": form,
                "item": instance,
                "slot_formset": slot_formset,
            },
        )

    post = request.POST.copy()
    prefix = f"slots-{slot_index}-opts"
    total = int(post.get(f"{prefix}-TOTAL_FORMS", 0))
    post[f"{prefix}-TOTAL_FORMS"] = total + 1

    # Rebuild all formsets from POST
    slot_formset = SlotFormSet(
        post,
        instance=instance,
        prefix="slots",
        club=request.club,
        container=instance,
    )
    return render(
        request,
        "items/form.html",
        {
            "form": form,
            "item": instance,
            "slot_formset": slot_formset,
        },
    )


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return None


def _with_item(target, pk):
    parts = urlsplit(target)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "item"] + [("item", str(pk))]
    return urlunsplit(("", "", parts.path, urlencode(query), parts.fragment))


def _int(raw):
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


@method_decorator(club_admin_required, name="dispatch")
class ReferencesView(ClubScopedMixin, View):
    def get(self, request, club_slug):
        g = request.GET
        value_cp = (
            _int(g.get("value_pp")) * CP_PER_PP
            + _int(g.get("value_gp")) * CP_PER_GP
            + _int(g.get("value_sp")) * CP_PER_SP
            + _int(g.get("value_cp"))
        )
        band = g.get("rarity", "")
        if band not in Rarity.values:
            band = ""
        items = reference_items(
            request.club,
            band,
            value_cp,
            g.get("ref_q", ""),
            exclude_pk=_int(g.get("exclude")) or None,
        )
        return render(request, "items/_references.html", {"items": items})


@method_decorator(club_admin_required, name="dispatch")
class CreateView(ClubScopedMixin, View):
    def get(self, request, club_slug):
        next_url = _safe_next(request)
        form = ItemForm(club=request.club)
        return render_modal_or_page(
            request,
            "items/_form_modal.html",
            "items/form.html",
            {"form": form, "item": None, "next_url": next_url},
        )

    def post(self, request, club_slug):
        _safe_next(request)
        return _create_form_view(request, Item(club=request.club))


@method_decorator(club_admin_required, name="dispatch")
class EditView(ClubScopedMixin, View):
    def get(self, request, club_slug, pk):
        item = self.get_club_object_or_404(Item, pk=pk)
        return _form_view(request, item)

    def post(self, request, club_slug, pk):
        item = self.get_club_object_or_404(Item, pk=pk)
        return _form_view(request, item)


def _set_retired(view, pk, value, text):
    item = view.get_club_object_or_404(Item, pk=pk)
    item.retired = value
    item.save(update_fields=["retired"])
    messages.success(view.request, f"{item.name} {text}.")
    return redirect("items:detail", club_slug=view.club.slug, pk=item.pk)


@method_decorator(club_admin_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class RetireView(ClubScopedMixin, ClubContextMixin, View):
    def post(self, request, club_slug, pk):
        return _set_retired(self, pk, True, "retired")


@method_decorator(club_admin_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class RestoreView(ClubScopedMixin, ClubContextMixin, View):
    def post(self, request, club_slug, pk):
        return _set_retired(self, pk, False, "restored")


@method_decorator(club_admin_required, name="dispatch")
@method_decorator(require_POST, name="dispatch")
class DeleteView(ClubScopedMixin, View):
    def post(self, request, club_slug, pk):
        item = self.get_club_object_or_404(Item, pk=pk)
        name = item.name
        if delete_or_retire(item):
            messages.success(request, f"Deleted {name}.")
            return redirect("items:index", club_slug=request.club.slug)
        messages.warning(request, f"{name} is in use, so it was retired instead.")
        return redirect("items:detail", club_slug=request.club.slug, pk=pk)


@method_decorator(admin_or_gm_required, name="dispatch")
class LootCardsPickerView(ClubScopedMixin, PermissionMixin, View):
    def get(self, request, club_slug):
        is_admin = self.is_club_admin(request.user, request.club)
        show_retired = is_admin and request.GET.get("retired") == "1"
        items = self.get_club_queryset(Item)
        if not show_retired:
            items = items.filter(retired=False)
        q = request.GET.get("q", "").strip()
        if q:
            items = items.filter(name__icontains=q)
        items = list(items)
        return render(
            request,
            "items/loot_cards_picker.html",
            {
                "items": items,
                "is_admin": is_admin,
                "show_retired": show_retired,
                "search_query": q,
                "retired_qs": "&retired=1" if show_retired else "",
            },
        )


@method_decorator(admin_or_gm_required, name="dispatch")
class LootCardsPrintView(ClubScopedMixin, PermissionMixin, View):
    def get(self, request, club_slug):
        copies = request.GET.get("copies", "type")
        if copies not in ("type", "item"):
            copies = "type"
        items = self.get_club_queryset(Item).filter(retired=False)
        pairs = []
        for item in items:
            qty = request.GET.get(f"qty_{item.pk}", "0")
            try:
                qty = max(int(qty), 0)
            except (TypeError, ValueError):
                qty = 0
            if qty > 0:
                pairs.append((item, qty))
        over = too_many(pairs, copies)
        cards = [] if over else build_cards(pairs, copies)
        sheets = [] if over else chunk(cards)
        empty_cells = range((-len(cards)) % CARDS_PER_SHEET) if not over else range(0)
        return render(
            request,
            "items/loot_cards_print.html",
            {
                "sheets": sheets,
                "cards": cards,
                "copies": copies,
                "too_many": over,
                "card_cap": CARD_CAP,
                "printed_on": timezone.localdate(),
                "owner": None,
                "empty_cells": empty_cells,
                "layout": "grid",
            },
        )
