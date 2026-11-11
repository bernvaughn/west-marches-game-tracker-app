from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import admin_or_gm_required
from accounts.scoping import club_get_object_or_404, club_queryset
from items.models import Item
from ledger.coins import CoinsField, format_coins

from ..models import ProposedItem

FILTERS = ["pending", "approved", "rejected", "all"]


class ProposedItemForm(forms.ModelForm):
    value = CoinsField(required=False, label="Value")
    description = forms.CharField(required=False, max_length=5000, widget=forms.Textarea)
    traits = forms.CharField(required=False, max_length=5000, widget=forms.Textarea)
    details = forms.CharField(required=False, max_length=5000, widget=forms.Textarea)

    class Meta:
        model = ProposedItem
        fields = ["name", "description", "traits", "details"]

    def __init__(self, *args, club, **kwargs):
        super().__init__(*args, **kwargs)
        self.club = club
        if self.instance.pk:
            self.initial["value"] = self.instance.value_cp

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Item.objects.for_club(self.club).filter(retired=False, name__iexact=name).exists():
            raise forms.ValidationError("An active item with this name already exists.")
        return name

    def save(self, commit=True):
        self.instance.value_cp = self.cleaned_data.get("value") or 0
        return super().save(commit=commit)


def _detail(request, p, form, status=200):
    return render(
        request,
        "agent_access/items/detail.html",
        {"p": p, "form": form, "value_text": format_coins(p.value_cp) if p.value_cp else ""},
        status=status,
    )


@admin_or_gm_required
def proposed_item_list(request, club_slug):
    status = request.GET.get("status", "pending")
    if status not in FILTERS:
        status = "pending"
    qs = club_queryset(request, ProposedItem).select_related("connection")
    if status != "all":
        qs = qs.filter(status=status)
    rows = [
        {"p": p, "value": format_coins(p.value_cp) if p.value_cp else ""}
        for p in qs.order_by("-created", "-pk")
    ]
    return render(
        request,
        "agent_access/items/list.html",
        {"rows": rows, "status": status, "filters": FILTERS},
    )


@admin_or_gm_required
def proposed_item_detail(request, club_slug, pk):
    p = club_get_object_or_404(request, ProposedItem, pk=pk)
    pending = p.status == ProposedItem.Status.PENDING
    if request.method == "POST":
        if not pending:
            messages.info(request, f"This proposal is already {p.status}.")
            return redirect("agent_access:proposed_item_detail", club_slug=club_slug, pk=p.pk)
        form = ProposedItemForm(request.POST, instance=p, club=request.club)
        if form.is_valid():
            form.save()
            messages.success(request, "Changes saved.")
            return redirect("agent_access:proposed_item_detail", club_slug=club_slug, pk=p.pk)
        return _detail(request, p, form)
    form = ProposedItemForm(instance=p, club=request.club) if pending else None
    return _detail(request, p, form)


@admin_or_gm_required
@require_POST
def proposed_item_approve(request, club_slug, pk):
    p = club_get_object_or_404(request, ProposedItem, pk=pk)
    form = ProposedItemForm(request.POST, instance=p, club=request.club)
    if p.status == ProposedItem.Status.PENDING and not form.is_valid():
        return _detail(request, p, form)
    with transaction.atomic():
        locked = club_queryset(request, ProposedItem).select_for_update().get(pk=pk)
        if locked.status != ProposedItem.Status.PENDING:
            messages.info(request, f"This proposal is already {locked.status}.")
            return redirect("agent_access:proposed_item_detail", club_slug=club_slug, pk=pk)
        form = ProposedItemForm(request.POST, instance=locked, club=request.club)
        if not form.is_valid():
            return _detail(request, locked, form)
        locked = form.save()
        locked.approved_item = Item.objects.create(
            club=request.club,
            name=locked.name,
            description=locked.description,
            traits=locked.traits,
            details=locked.details,
            value_cp=locked.value_cp,
        )
        locked.status = ProposedItem.Status.APPROVED
        locked.save()
    messages.success(request, f"Approved. “{locked.name}” is now in the catalogue.")
    return redirect("agent_access:proposed_item_detail", club_slug=club_slug, pk=pk)


@admin_or_gm_required
@require_POST
def proposed_item_reject(request, club_slug, pk):
    club_get_object_or_404(request, ProposedItem, pk=pk)
    with transaction.atomic():
        locked = club_queryset(request, ProposedItem).select_for_update().get(pk=pk)
        if locked.status != ProposedItem.Status.PENDING:
            messages.info(request, f"This proposal is already {locked.status}.")
        else:
            locked.status = ProposedItem.Status.REJECTED
            locked.save(update_fields=["status"])
            messages.success(request, "Proposal rejected.")
    return redirect("agent_access:proposed_items", club_slug=club_slug)
