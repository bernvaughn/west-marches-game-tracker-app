from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import club_admin_required
from accounts.scoping import club_get_object_or_404
from shops.models import Rotation


@club_admin_required
def rotation_list(request, club_slug):
    return render(request, "shops/rotations/list.html")


@club_admin_required
def rotation_create(request, club_slug):
    return render(request, "shops/rotations/form.html")


@club_admin_required
def rotation_edit(request, club_slug, rotation_id):
    rotation = club_get_object_or_404(request, Rotation, pk=rotation_id)
    return render(request, "shops/rotations/form.html", {"rotation": rotation})


@club_admin_required
@require_POST
def rotation_delete(request, club_slug, rotation_id):
    club_get_object_or_404(request, Rotation, pk=rotation_id)
    return redirect("shops:rotation_list", club_slug=club_slug)
