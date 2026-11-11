from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import club_admin_required, club_member_required, is_club_admin
from accounts.scoping import club_get_object_or_404, club_queryset

from .forms import ItemForm
from .models import Item
from .services import delete_or_retire


@club_member_required
def index(request, club_slug):
    is_admin = is_club_admin(request.user, request.club)
    show_retired = is_admin and request.GET.get("retired") == "1"
    items = club_queryset(request, Item)
    if not show_retired:
        items = items.filter(retired=False)
    return render(
        request,
        "items/index.html",
        {"items": items, "is_admin": is_admin, "show_retired": show_retired},
    )


@club_member_required
def detail(request, club_slug, pk):
    item = club_get_object_or_404(request, Item, pk=pk)
    is_admin = is_club_admin(request.user, request.club)
    if item.retired and not is_admin:
        raise Http404
    return render(request, "items/detail.html", {"item": item, "is_admin": is_admin})


def _form_view(request, instance):
    form = ItemForm(request.POST or None, instance=instance, club=request.club)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        messages.success(request, f"Saved {item.name}.")
        return redirect("items:detail", club_slug=request.club.slug, pk=item.pk)
    return render(request, "items/form.html", {"form": form, "item": instance})


@club_admin_required
def create(request, club_slug):
    return _form_view(request, None)


@club_admin_required
def edit(request, club_slug, pk):
    return _form_view(request, club_get_object_or_404(request, Item, pk=pk))


def _set_retired(request, pk, value, text):
    item = club_get_object_or_404(request, Item, pk=pk)
    item.retired = value
    item.save(update_fields=["retired"])
    messages.success(request, f"{item.name} {text}.")
    return redirect("items:detail", club_slug=request.club.slug, pk=item.pk)


@club_admin_required
@require_POST
def retire(request, club_slug, pk):
    return _set_retired(request, pk, True, "retired")


@club_admin_required
@require_POST
def restore(request, club_slug, pk):
    return _set_retired(request, pk, False, "restored")


@club_admin_required
@require_POST
def delete(request, club_slug, pk):
    item = club_get_object_or_404(request, Item, pk=pk)
    name = item.name
    if delete_or_retire(item):
        messages.success(request, f"Deleted {name}.")
        return redirect("items:index", club_slug=request.club.slug)
    messages.warning(request, f"{name} is in use, so it was retired instead.")
    return redirect("items:detail", club_slug=request.club.slug, pk=pk)
