import json
from datetime import date

from django.contrib import messages as flash
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from items.models import Item
from ledger.coins import format_coins
from ledger.services import LedgerError, Line, record
from map import services as map_services
from map.models import HexMap, Location
from player_characters.forms import formset_lines, item_line_formset
from player_characters.models import Character
from player_characters.selection import selected_character

from ..forms.grants import GRANT_FORMS, GRANT_TITLES, MapGrantForm
from ..forms.inbox import (
    STATUS_ACTIONS,
    TEMPLATE_TEXTS,
    BulkStatusForm,
    MessageForm,
    StatusForm,
    StockRequestForm,
    allowed_statuses,
)
from ..htmx import is_htmx, render_modal_or_page
from ..models import Message
from ..permissions import admin_or_gm_required, club_admin_required, club_member_required
from ..scoping import club_get_object_or_404, club_queryset

FILTERS = ("open", "handled", "closed", "all")
KIND_FILTERS = (
    ("all", "All"),
    ("message", "Messages"),
    ("stock_request", "Stock requests"),
    ("starting_request", "Starting requests"),
)

# Session-based batch storage for grant accumulation
BATCH_SESSION_KEY = "wm_grant_batch"


# Session-based batch storage helpers
def _batch_get(request, msg_pk):
    """Get the batch of grants for a message from the session."""
    batch = request.session.get(BATCH_SESSION_KEY, {})
    return list(batch.get(str(msg_pk), []))


def _batch_set(request, msg_pk, grants):
    """Set the batch of grants for a message in the session."""
    batch = request.session.get(BATCH_SESSION_KEY, {})
    batch[str(msg_pk)] = grants
    request.session[BATCH_SESSION_KEY] = batch


def _batch_clear(request, msg_pk):
    """Clear the batch of grants for a message from the session."""
    batch = request.session.get(BATCH_SESSION_KEY, {})
    if str(msg_pk) in batch:
        del batch[str(msg_pk)]
        request.session[BATCH_SESSION_KEY] = batch


def _send(request, club_slug, *, kind, form_class, template, url_name, flash_text, initial=None):
    membership = request.membership
    if membership is None:
        if request.method == "POST":
            raise PermissionDenied
        return render(request, template, {"form": None, "sent": []})
    character = selected_character(request)
    form = form_class(request.POST or None, initial=initial) if character is not None else None
    if request.method == "POST" and form is not None and form.is_valid():
        msg = form.save(commit=False)
        msg.character = character
        msg.club = request.club
        msg.sender = membership
        msg.kind = kind
        msg.save()
        flash.success(request, flash_text)
        return redirect(url_name, club_slug=club_slug)
    sent = (
        club_queryset(request, Message)
        .filter(sender=membership, kind=kind)
        .select_related("character")
    )
    return render(
        request,
        template,
        {"form": form, "sent": sent, "character": character, "is_member": True},
    )


@club_member_required
def message_new(request, club_slug):
    initial = {}
    character = selected_character(request)
    template_key = request.GET.get("template")
    if template_key and character is not None:
        template_text = TEMPLATE_TEXTS.get(template_key)
        if template_text is not None:
            initial["body"] = template_text.replace("{character}", character.name)
    return _send(
        request,
        club_slug,
        kind=Message.Kind.MESSAGE,
        form_class=MessageForm,
        template="accounts/inbox/message_new.html",
        url_name="accounts:message_new",
        flash_text="Message sent to the club admins.",
        initial=initial,
    )


@club_member_required
def stock_request_new(request, club_slug):
    return _send(
        request,
        club_slug,
        kind=Message.Kind.STOCK_REQUEST,
        form_class=StockRequestForm,
        template="accounts/inbox/stock_request_new.html",
        url_name="accounts:stock_request_new",
        flash_text="Stock request sent to the club admins.",
    )


@admin_or_gm_required
def message_inbox(request, club_slug):
    return _render_inbox(request)


def _render_inbox(request):
    """Shared context builder for the inbox page (filters, kind, messages list)."""
    status = request.GET.get("status", "open")
    if status not in FILTERS:
        status = "open"
    qs = (
        club_queryset(request, Message)
        .select_related("sender__user", "character")
        .prefetch_related(
            "starting_request__item",
            "granted_entries__lines__item",
            "granted_entries__character",
            "granted_visits__character",
            "granted_visits__map",
            "granted_credits__credit__location",
            "granted_credits__character",
            "granted_found_marks__location",
            "granted_found_marks__character",
        )
    )
    kind = _kind_of(request.GET)
    if status != "all":
        qs = qs.filter(status=status)
    if kind != "all":
        qs = qs.filter(kind=kind)
    return render(
        request,
        "accounts/inbox/inbox.html",
        {
            "messages_list": qs,
            "status": status,
            "filters": FILTERS,
            "kind": kind,
            "kind_filters": KIND_FILTERS,
        },
    )


def _filter_of(data):
    back = data.get("filter", "open")
    return back if back in FILTERS else "open"


def _kind_of(data):
    kind = data.get("kind", "all")
    return kind if kind in {k for k, _ in KIND_FILTERS} else "all"


def _inbox_url(club_slug, back, kind="all"):
    return f"{reverse('accounts:message_inbox', args=[club_slug])}?status={back}&kind={kind}"


def _modal_done():
    response = HttpResponse(status=204)
    response["HX-Trigger"] = json.dumps({"appModalClose": True, "inboxChanged": True})
    return response


@club_admin_required
def message_status_confirm(request, club_slug, pk, status):
    msg = club_get_object_or_404(request, Message, pk=pk)
    if status not in allowed_statuses(msg):
        raise Http404
    ctx = {
        "msg": msg,
        "status": status,
        "action": STATUS_ACTIONS[status],
        "filter": _filter_of(request.GET),
        "kind": _kind_of(request.GET),
    }
    return render_modal_or_page(
        request,
        "accounts/inbox/_status_confirm.html",
        "accounts/inbox/status_confirm.html",
        ctx,
    )


@club_admin_required
@require_POST
def message_status(request, club_slug, pk):
    msg = club_get_object_or_404(request, Message, pk=pk)
    form = StatusForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid status")
    msg.status = form.cleaned_data["status"]
    msg.save(update_fields=["status"])
    if is_htmx(request):
        return _modal_done()
    return redirect(_inbox_url(club_slug, _filter_of(request.POST), _kind_of(request.POST)))


@club_admin_required
@require_POST
def message_bulk_status(request, club_slug):
    form = BulkStatusForm(request.POST, club=request.club)
    if not form.is_valid():
        return HttpResponseBadRequest("Invalid bulk status request")
    message_ids = request.POST.getlist("message_ids")
    if not message_ids:
        return HttpResponseBadRequest("No messages selected")
    status = form.cleaned_data["status"]
    club_queryset(request, Message).filter(pk__in=message_ids).update(status=status)
    if is_htmx(request):
        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({"inboxChanged": True})
        return response
    flash.success(request, "Status updated for the selected messages.")
    return redirect(_inbox_url(club_slug, _filter_of(request.POST), _kind_of(request.POST)))


def _apply_grant(request, msg, kind, data, lines):
    """Write the grant through the ledger and map services. Raise LedgerError to roll back."""
    character, date, note = data["character"], data["date"], data["note"]
    lines = list(lines)
    if kind == "coins":
        lines.append(Line(coins=data["coins"]))
    with transaction.atomic():
        if lines:
            record(
                character,
                "award",
                lines,
                note=note,
                date=date,
                actor=request.user,
                source_message=msg,
            )
        map_kind = data.get("map_kind") if kind == "map" else None
        location = data.get("location")
        if map_kind == "visit":
            if location is not None:
                hex_map, q, r = location.tile.map, location.tile.q, location.tile.r
            else:
                hex_map, q, r = data["hex_map"], data["q"], data["r"]
            map_services.record_visits(hex_map, q, r, [character], date, source_message=msg)
        elif map_kind in ("discovered", "explored"):
            map_services.add_to_credit(location, map_kind, [character], date, source_message=msg)
        elif map_kind == "found":
            map_services.add_found_marks(
                location, [character], date, created_by=request.membership, source_message=msg
            )
        if data["mark_handled"]:
            msg.status = Message.Status.HANDLED
            msg.save(update_fields=["status"])


def _apply_batch_grant(request, msg, batch, club):
    """Apply a batch of grants, producing one ledger entry per type.
    Raise LedgerError to roll back.

    Grant dict structure (stored as primitives in session):
    - kind: "coins" | "items" | "map"
    - character_pk: int (fetched with club scoping)
    - coins: int (for coins type)
    - item_tuples: [(item_pk, quantity), ...] (for items type)
    - map_kind: str
    - location_pk: int (fetched with club scoping)
    - hex_map_pk, q, r: (for visit type)
    - note: str
    - date: ISO date string (fetched as date object)
    - mark_handled: bool
    """
    with transaction.atomic():
        # Group grants by type: coins, items, map
        coins_total = 0
        item_tuples = []  # List of (item_pk, quantity)
        map_entries = []  # List of grant dicts for map operations

        first_grant = batch[0]
        character = club_queryset(request, Character).get(pk=first_grant["character_pk"])
        date_val = first_grant["date"]
        if isinstance(date_val, str):
            date_val = date.fromisoformat(date_val)
        note = first_grant["note"]
        mark_handled = any(g.get("mark_handled") for g in batch)

        for grant in batch:
            grant_kind = grant["kind"]
            if grant_kind == "coins":
                coins_total += grant["coins"]
            elif grant_kind == "items":
                for item_pk, qty in grant.get("item_tuples", []):
                    item_tuples.append((item_pk, qty))
            elif grant_kind == "map":
                map_entries.append(grant)

        # Process coins - one ledger entry
        if coins_total != 0 or mark_handled:
            lines = [Line(coins=coins_total)]
            record(
                character,
                "award",
                lines,
                note=note,
                date=date_val,
                actor=request.user,
                source_message=msg,
            )

        # Process items - one ledger entry
        if item_tuples:
            from items.models import Item
            from ledger.services import Line as LedgerLine

            items_qs = Item.objects.for_club(club)
            item_map = {item.pk: item for item in items_qs}
            lines = [
                LedgerLine(item=item_map[pk], quantity=qty)
                for pk, qty in item_tuples
                if pk in item_map
            ]
            record(
                character,
                "award",
                lines,
                note=note,
                date=date_val,
                actor=request.user,
                source_message=msg,
            )

        # Process map credits - each entry per grant type
        for grant in map_entries:
            map_kind = grant.get("map_kind")
            location = None
            hex_map = None
            q, r = grant.get("q"), grant.get("r")

            if grant.get("location_pk"):
                location = club_queryset(request, Location).get(pk=grant["location_pk"])
            elif grant.get("hex_map_pk"):
                hex_map = club_queryset(request, HexMap).get(pk=grant["hex_map_pk"])

            if map_kind == "visit":
                if location is not None:
                    hex_map, q, r = location.tile.map, location.tile.q, location.tile.r
                if hex_map is not None:
                    map_services.record_visits(
                        hex_map, q, r, [character], date_val, source_message=msg
                    )
            elif map_kind in ("discovered", "explored"):
                if location is not None:
                    map_services.add_to_credit(
                        location, map_kind, [character], date_val, source_message=msg
                    )
            elif map_kind == "found":
                if location is not None:
                    map_services.add_found_marks(
                        location,
                        [character],
                        date_val,
                        created_by=request.membership,
                        source_message=msg,
                    )

        # Mark message handled if any grant requested it
        if mark_handled:
            msg.status = Message.Status.HANDLED
            msg.save(update_fields=["status"])


def _summary(kind, data, lines):
    """(label, value) rows describing what a confirmed grant will write."""
    rows = [("Character", data["character"].name)]
    if kind == "coins":
        rows.append(("Coins", format_coins(data["coins"])))
    elif kind == "items":
        rows.append(("Items", ", ".join(f"{ln.item.name} × {ln.quantity}" for ln in lines)))
    else:
        label = dict(MapGrantForm.MAP_KINDS)[data["map_kind"]]
        location = data.get("location")
        if location is not None:
            tile = location.tile
            where = f"{location.name} ({tile.map.name} {tile.q}, {tile.r})"
        else:
            where = f"{data['hex_map'].name} ({data['q']}, {data['r']})"
        rows.append(("Map credit", f"{label}: {where}"))
    rows += [
        ("Note", data["note"]),
        ("Date", data["date"].isoformat()),
        ("Marks the message handled", "Yes" if data["mark_handled"] else "No"),
    ]
    return rows


_NOT_CARRIED = {"csrfmiddlewaretoken", "confirmed", "edit", "action"}


@club_admin_required
def message_give(request, club_slug, pk, kind):
    msg = club_get_object_or_404(request, Message, pk=pk)
    if msg.kind == Message.Kind.STOCK_REQUEST:
        raise Http404

    # Clear batch on fresh GET of the form
    if request.method == "GET":
        _batch_clear(request, pk)

    post = request.method == "POST"
    data = request.POST if post else None
    kwargs = {
        "characters_qs": club_queryset(request, Character).order_by("name"),
        "message": msg,
    }
    if kind == "map":
        kwargs["locations_qs"] = club_queryset(request, Location).select_related("tile__map")
        kwargs["maps_qs"] = club_queryset(request, HexMap)
    form = GRANT_FORMS[kind](data, **kwargs)
    formset = None
    if kind == "items":
        items = Item.objects.for_club(request.club).filter(retired=False)
        formset = item_line_formset(items, data, extra=3)

    back = _filter_of(data or request.GET)

    # Handle batch flow
    action = data.get("action") if post else request.GET.get("action")

    # GET with action=batch_review: show batch confirm page
    if post and action == "review":
        batch = _batch_get(request, pk)
        if not batch:
            # Show review page even if empty - will error on confirm
            ctx = _build_context(request, msg, kind, form, formset, back, pk, batch)
            return render_modal_or_page(
                request,
                "accounts/inbox/_give_confirm.html",
                "accounts/inbox/give_confirm.html",
                ctx,
            )

        # Build summary for batch (fetch models for display)
        summary_items = []
        for grant in batch:
            if grant["kind"] == "coins":
                summary_items.append(f" Coins: {format_coins(grant['coins'])}")
            elif grant["kind"] == "items":
                items_str = ", ".join(
                    f"Item × {qty}" for item_pk, qty in grant.get("item_tuples", [])
                )
                summary_items.append(f" Items: {items_str}")
            elif grant["kind"] == "map":
                label = dict(MapGrantForm.MAP_KINDS).get(grant.get("map_kind"), "Map")
                summary_items.append(f" Map: {label}")

        ctx = {
            "msg": msg,
            "kind": kind,
            "title": f"Review batch for {GRANT_TITLES[kind]}",
            "form": form,
            "formset": formset,
            "filter": back,
            "give_url": reverse(f"accounts:message_give_{kind}", args=[msg.club.slug, msg.pk]),
            "batch": batch,
            "batch_summary": summary_items,
            "carry": [],
        }
        return render_modal_or_page(
            request,
            "accounts/inbox/_give_confirm.html",
            "accounts/inbox/give_confirm.html",
            ctx,
        )

    # Handle add to batch
    if post and action == "add" and form.is_valid():
        lines = []
        if kind == "items" and formset is not None:
            if formset.is_valid():
                lines = formset_lines(formset, 1)
                if not lines:
                    form.add_error(None, "Add at least one item.")

        if form.is_valid() and (kind != "items" or lines):
            # Build grant dict from form data - STORE PRIMITIVES ONLY
            grant = {
                "kind": kind,
                "character_pk": form.cleaned_data["character"].pk,
                "date": form.cleaned_data["date"].isoformat(),
                "note": form.cleaned_data["note"],
                "mark_handled": form.cleaned_data.get("mark_handled", True),
            }
            if kind == "coins":
                grant["coins"] = form.cleaned_data.get("coins", 0)
            if kind == "items":
                grant["item_tuples"] = [(ln.item.pk, ln.quantity) for ln in lines]
            if kind == "map":
                grant["map_kind"] = form.cleaned_data.get("map_kind")
                loc = form.cleaned_data.get("location")
                grant["location_pk"] = loc.pk if loc else None
                hmap = form.cleaned_data.get("hex_map")
                grant["hex_map_pk"] = hmap.pk if hmap else None
                grant["q"] = form.cleaned_data.get("q")
                grant["r"] = form.cleaned_data.get("r")

            # Add to batch
            batch = _batch_get(request, pk)
            batch.append(grant)
            _batch_set(request, pk, batch)

            # Return empty form (HTMX or full page)
            form = GRANT_FORMS[kind](None, **kwargs)
            if formset is not None:
                formset = item_line_formset(items, None, extra=3)
            ctx = _build_context(request, msg, kind, form, formset, back, pk, batch)
            return render_modal_or_page(
                request, "accounts/inbox/_give_form.html", "accounts/inbox/give.html", ctx
            )

    # Handle back from review - preserve batch
    if post and action == "edit":
        batch = _batch_get(request, pk)
        ctx = _build_context(request, msg, kind, form, formset, back, pk, batch)
        return render_modal_or_page(
            request,
            "accounts/inbox/_give_confirm.html",
            "accounts/inbox/give_confirm.html",
            ctx,
        )

    # Handle confirm batch (only if batch has items)
    if post and data.get("confirmed"):
        batch = _batch_get(request, pk)
        if batch:
            # Apply batch
            try:
                _apply_batch_grant(request, msg, batch, request.club)
            except LedgerError as exc:
                form.add_error(None, str(exc))
                ctx = _build_context(request, msg, kind, form, formset, back, pk, batch)
                return render_modal_or_page(
                    request,
                    "accounts/inbox/_give_confirm.html",
                    "accounts/inbox/give_confirm.html",
                    ctx,
                )
            else:
                _batch_clear(request, pk)
                if is_htmx(request):
                    return _modal_done()
                flash.success(request, f"Batch grant done from message #{msg.pk}.")
                return redirect(_inbox_url(club_slug, back))
            # If batch is empty, fall through to single-grant logic below

    # Normal form flow (not batch)
    fill = ("accounts/inbox/_give_form.html", "accounts/inbox/give.html")
    # Use all() for cleaner check
    no_action = all(k not in request.POST for k in ("add", "edit", "review"))
    if post and no_action:
        valid = form.is_valid()
        if formset is not None:
            valid = formset.is_valid() and valid
        if valid:
            lines = formset_lines(formset, 1) if formset is not None else []
            if kind == "items" and not lines:
                form.add_error(None, "Add at least one item.")
            elif request.POST.get("confirmed"):
                try:
                    _apply_grant(request, msg, kind, form.cleaned_data, lines)
                except LedgerError as exc:
                    form.add_error(None, str(exc))
                else:
                    if is_htmx(request):
                        return _modal_done()
                    flash.success(request, f"{GRANT_TITLES[kind]} done from message #{msg.pk}.")
                    return redirect(_inbox_url(club_slug, back))
            else:
                # Show review page for single-grant flow
                ctx = _build_context(request, msg, kind, form, formset, back, pk, [])
                ctx["summary"] = _summary(kind, form.cleaned_data, lines)
                ctx["carry"] = [
                    (name, value)
                    for name, values in request.POST.lists()
                    if name not in _NOT_CARRIED
                    for value in values
                ]
                return render_modal_or_page(
                    request,
                    "accounts/inbox/_give_confirm.html",
                    "accounts/inbox/give_confirm.html",
                    ctx,
                )

    # Build context for final render
    batch = _batch_get(request, pk) if request.method == "POST" else []
    ctx = _build_context(request, msg, kind, form, formset, back, pk, batch)
    return render_modal_or_page(request, *fill, ctx)


def _build_context(request, msg, kind, form, formset, back, pk, batch):
    """Build context dictionary for grant forms."""
    ctx = {
        "msg": msg,
        "kind": kind,
        "title": GRANT_TITLES[kind],
        "form": form,
        "formset": formset,
        "filter": back,
        "give_url": reverse(f"accounts:message_give_{kind}", args=[msg.club.slug, msg.pk]),
        "batch": batch,
    }
    return ctx


@club_member_required
def message_detail(request, club_slug, pk):
    """Read-only view of a message for the sender (player) or club admins."""
    msg = club_get_object_or_404(request, Message, pk=pk)

    # Check permissions: only sender or club admins/GM can view
    membership = request.membership
    if msg.sender_id != membership.id:
        if not (membership.is_game_master or membership.is_club_admin):
            raise Http404

    return render(
        request,
        "accounts/inbox/message_detail.html",
        {
            "msg": msg,
            "is_sender": msg.sender_id == membership.id,
            "is_admin": membership.is_game_master or membership.is_club_admin,
        },
    )
