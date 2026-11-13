import json

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
    MessageForm,
    StatusForm,
    StockRequestForm,
    allowed_statuses,
)
from ..htmx import is_htmx, render_modal_or_page
from ..models import Message
from ..permissions import club_admin_required, club_member_required
from ..scoping import club_get_object_or_404, club_queryset

FILTERS = ("open", "handled", "closed", "all")
KIND_FILTERS = (
    ("all", "All"),
    ("message", "Messages"),
    ("stock_request", "Stock requests"),
)


def _send(request, club_slug, *, kind, form_class, template, url_name, flash_text):
    membership = request.membership
    if membership is None:
        if request.method == "POST":
            raise PermissionDenied
        return render(request, template, {"form": None, "sent": []})
    character = selected_character(request)
    form = form_class(request.POST or None) if character is not None else None
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
    return _send(
        request,
        club_slug,
        kind=Message.Kind.MESSAGE,
        form_class=MessageForm,
        template="accounts/inbox/message_new.html",
        url_name="accounts:message_new",
        flash_text="Message sent to the club admins.",
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


@club_admin_required
def message_inbox(request, club_slug):
    status = request.GET.get("status", "open")
    if status not in FILTERS:
        status = "open"
    qs = (
        club_queryset(request, Message)
        .select_related("sender__user", "character")
        .prefetch_related(
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


_NOT_CARRIED = {"csrfmiddlewaretoken", "confirmed", "edit"}


@club_admin_required
def message_give(request, club_slug, pk, kind):
    msg = club_get_object_or_404(request, Message, pk=pk)
    if msg.kind == Message.Kind.STOCK_REQUEST:
        raise Http404
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
    ctx = {
        "msg": msg,
        "kind": kind,
        "title": GRANT_TITLES[kind],
        "form": form,
        "formset": formset,
        "filter": back,
        "give_url": reverse(f"accounts:message_give_{kind}", args=[club_slug, msg.pk]),
    }
    fill = ("accounts/inbox/_give_form.html", "accounts/inbox/give.html")
    if post and "edit" not in request.POST:
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
    return render_modal_or_page(request, *fill, ctx)
