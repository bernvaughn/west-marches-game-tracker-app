from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import game_master_required
from accounts.scoping import club_get_object_or_404

from ..forms_batches import LineForm
from ..models import ProposedBatch, ProposedLine
from ..services.confirm import ConfirmError, confirm_batch


def _to_detail(club_slug, pk):
    return redirect("agent_access:batch_detail", club_slug=club_slug, pk=pk)


@game_master_required
def batch_list(request, club_slug):
    batches = ProposedBatch.objects.for_club(request.club).select_related("user", "connection")
    batches = batches.annotate(line_count=Count("lines"))
    pending = batches.filter(status=ProposedBatch.Status.PENDING).order_by("-created")
    recent = batches.filter(
        status__in=[ProposedBatch.Status.CONFIRMED, ProposedBatch.Status.REVERSED]
    ).order_by("-created")[:20]
    return render(request, "agent_access/batches/list.html", {"pending": pending, "recent": recent})


def _render_detail(request, batch, bound=None, status=200):
    lines = list(batch.lines.select_related("character", "item", "proposed_item").order_by("pk"))
    rows = []
    for n, line in enumerate(lines, start=1):
        form = None
        if batch.status == ProposedBatch.Status.PENDING:
            if bound is not None and bound.prefix == f"line-{line.pk}":
                form = bound
            else:
                form = LineForm(club=request.club, line=line)
        rows.append({"n": n, "line": line, "form": form})
    ctx = {"batch": batch, "rows": rows, "pending": batch.status == ProposedBatch.Status.PENDING}
    return render(request, "agent_access/batches/detail.html", ctx, status=status)


@game_master_required
def batch_detail(request, club_slug, pk):
    batch = club_get_object_or_404(request, ProposedBatch, pk=pk)
    return _render_detail(request, batch)


@game_master_required
@require_POST
def batch_line_edit(request, club_slug, pk, line_pk):
    batch = club_get_object_or_404(request, ProposedBatch, pk=pk)
    line = club_get_object_or_404(request, ProposedLine, pk=line_pk, batch=batch)
    if batch.status != ProposedBatch.Status.PENDING:
        messages.error(request, "Only pending batches can be edited.")
        return _to_detail(club_slug, batch.pk)
    form = LineForm(request.POST, club=request.club, line=line)
    if not form.is_valid():
        return _render_detail(request, batch, bound=form, status=400)
    d = form.cleaned_data
    line.character = d["character"]
    line.item = d["item"]
    line.proposed_item = d["proposed_item"]
    line.quantity = d["quantity"] or 0
    line.coins = d["coins"] or 0
    line.note = d["note"]
    line.date = d["date"]
    line.save()
    messages.success(request, "Line saved.")
    return _to_detail(club_slug, batch.pk)


@game_master_required
@require_POST
def batch_line_remove(request, club_slug, pk, line_pk):
    batch = club_get_object_or_404(request, ProposedBatch, pk=pk)
    line = club_get_object_or_404(request, ProposedLine, pk=line_pk, batch=batch)
    if batch.status != ProposedBatch.Status.PENDING:
        messages.error(request, "Only pending batches can be edited.")
    else:
        line.delete()
        messages.success(request, "Line removed.")
    return _to_detail(club_slug, batch.pk)


@game_master_required
@require_POST
def batch_confirm(request, club_slug, pk):
    batch = club_get_object_or_404(request, ProposedBatch, pk=pk)
    try:
        entries = confirm_batch(club=request.club, batch_id=batch.pk, actor=request.user)
    except ConfirmError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        messages.success(request, f"Batch #{batch.pk} confirmed: {len(entries)} entries.")
    return _to_detail(club_slug, batch.pk)


@game_master_required
@require_POST
def batch_discard(request, club_slug, pk):
    batch = club_get_object_or_404(request, ProposedBatch, pk=pk)
    if batch.status != ProposedBatch.Status.PENDING:
        messages.error(request, "Only pending batches can be discarded.")
        return _to_detail(club_slug, batch.pk)
    batch.status = ProposedBatch.Status.DISCARDED
    batch.save(update_fields=["status"])
    messages.success(request, f"Batch #{batch.pk} discarded.")
    return redirect("agent_access:batches", club_slug=club_slug)
