"""Admin views for character options: species, classes, backgrounds."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.htmx import hx_response, is_htmx, render_modal_or_page
from accounts.permissions import is_club_admin
from character_options.forms import OptionForm
from character_options.kinds import get_kind
from character_options.services import (
    annotate_usage,
    delete_blockers,
    move_option,
    rename_option,
)


def option_admin_required(view):
    """Decorator: login required, then Http404 if not club admin.

    Unlike club_admin_required (which raises PermissionDenied -> 403),
    this gives 404 for GMs and players, as the spec requires.
    """

    @login_required
    def wrapper(request, club_slug, *args, **kwargs):
        club = getattr(request, "club", None)
        if club is None or club.slug != club_slug:
            raise Http404
        if not is_club_admin(request.user, club):
            raise Http404
        return view(request, club, *args, **kwargs)

    return wrapper


@option_admin_required
def index(request, club):
    """Redirect to the species list (nav target)."""
    return redirect("character_options:list", club_slug=club.slug, kind="species")


@option_admin_required
def list_options(request, club, kind):
    """List all options for a kind (active and archived), with usage counts."""
    kind_obj = get_kind(kind)
    model = kind_obj.model

    # Get all records (active and archived) with usage annotations
    qs = model.objects.for_club(club).order_by("sort_order", "name")
    qs = annotate_usage(qs, kind)

    ctx = {
        "club": club,
        "kind": kind,
        "kind_obj": kind_obj,
        "options": qs,
    }
    return render(request, "character_options/list.html", ctx)


def _option_form_view(request, club, kind, instance=None):
    """Shared form view for creating or editing an option."""
    kind_obj = get_kind(kind)
    is_create = instance is None

    def render_form(form, status=200):
        ctx = {
            "club": club,
            "kind": kind,
            "kind_obj": kind_obj,
            "form": form,
            "is_create": is_create,
        }
        if not is_create:
            ctx["option"] = instance
        return render_modal_or_page(
            request,
            "character_options/_form_modal.html",
            "character_options/form.html",
            ctx,
            status=status,
        )

    if request.method == "GET":
        return render_form(OptionForm(club=club, kind_slug=kind, instance=instance))

    # POST
    form = OptionForm(request.POST, club=club, kind_slug=kind, instance=instance)
    if form.is_valid():
        try:
            if is_create:
                form.save()
            else:
                rename_option(kind, instance, form.cleaned_data["name"])
        except IntegrityError:
            form.add_error(
                "name",
                f"A {kind_obj.singular.lower()} with this name already exists.",
            )
        else:
            verb = "created." if is_create else "renamed."
            messages.success(request, f"{kind_obj.singular} {verb}")
            if is_htmx(request):
                return hx_response(trigger={"optionsChanged": True, "appModalClose": True})
            return redirect("character_options:list", club_slug=club.slug, kind=kind)

    # Invalid form
    return render_form(form, status=400 if is_htmx(request) else 200)


@option_admin_required
def create_option_view(request, club, kind):
    """Create a new option (modal GET, modal POST)."""
    return _option_form_view(request, club, kind)


@option_admin_required
def edit_option(request, club, kind, pk):
    """Edit an option (modal GET, modal POST)."""
    kind_obj = get_kind(kind)
    model = kind_obj.model
    option = get_object_or_404(model.objects.for_club(club), pk=pk)
    return _option_form_view(request, club, kind, option)


@option_admin_required
@require_POST
def archive_option(request, club, kind, pk):
    """Archive an option (POST only, works without JS)."""
    kind_obj = get_kind(kind)
    model = kind_obj.model
    option = get_object_or_404(model.objects.for_club(club), pk=pk)
    option.is_active = False
    option.save(update_fields=["is_active"])
    messages.success(request, f"{kind_obj.singular} archived.")
    return redirect("character_options:list", club_slug=club.slug, kind=kind)


@option_admin_required
@require_POST
def restore_option(request, club, kind, pk):
    """Restore an archived option (POST only, works without JS)."""
    kind_obj = get_kind(kind)
    model = kind_obj.model
    option = get_object_or_404(model.objects.for_club(club), pk=pk)
    option.is_active = True
    option.save(update_fields=["is_active"])
    messages.success(request, f"{kind_obj.singular} restored.")
    return redirect("character_options:list", club_slug=club.slug, kind=kind)


@option_admin_required
def delete_option(request, club, kind, pk):
    """Delete an option: GET shows confirm, POST deletes (blocked if in use)."""
    kind_obj = get_kind(kind)
    model = kind_obj.model
    option = get_object_or_404(model.objects.for_club(club), pk=pk)

    blocker = delete_blockers(kind, option)

    if request.method == "GET":
        ctx = {
            "club": club,
            "kind": kind,
            "kind_obj": kind_obj,
            "option": option,
            "blocker": blocker,
            "confirm_url": reverse("character_options:delete", args=[club.slug, kind, pk]),
            "list_url": reverse("character_options:list", args=[club.slug, kind]),
        }
        return render_modal_or_page(
            request,
            "character_options/_delete_modal.html",
            "character_options/delete.html",
            ctx,
        )

    # POST - re-check blockers
    blocker = delete_blockers(kind, option)
    if blocker:
        if is_htmx(request):
            ctx = {
                "club": club,
                "kind": kind,
                "kind_obj": kind_obj,
                "option": option,
                "blocker": blocker,
                "confirm_url": reverse("character_options:delete", args=[club.slug, kind, pk]),
                "list_url": reverse("character_options:list", args=[club.slug, kind]),
            }
            return render(request, "character_options/_delete_modal.html", ctx, status=400)
        messages.error(request, blocker)
        return redirect("character_options:list", club_slug=club.slug, kind=kind)

    option.delete()
    messages.success(request, f"{kind_obj.singular} deleted.")
    if is_htmx(request):
        return hx_response(trigger={"optionsChanged": True, "appModalClose": True})
    return redirect("character_options:list", club_slug=club.slug, kind=kind)


@option_admin_required
@require_POST
def move_option_view(request, club, kind, pk):
    """Move an option up or down (POST only, works without JS)."""
    kind_obj = get_kind(kind)
    model = kind_obj.model
    option = get_object_or_404(model.objects.for_club(club), pk=pk)

    direction = request.POST.get("direction")
    if direction not in ("up", "down"):
        return HttpResponse(status=400)

    move_option(option, direction)
    return redirect("character_options:list", club_slug=club.slug, kind=kind)
