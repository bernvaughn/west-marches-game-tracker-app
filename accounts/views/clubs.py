from django.db import transaction
from django.db.models import Count
from django.shortcuts import render

from map.xp import copy_default_xp_table

from ..forms.clubs import ClubCreateForm
from ..models import Club
from ..passwords import get_or_create_member
from ..permissions import site_admin_required


@site_admin_required
def club_list(request):
    clubs = Club.objects.annotate(member_count=Count("memberships")).order_by("name")
    return render(request, "accounts/clubs/list.html", {"clubs": clubs})


@site_admin_required
def club_new(request):
    form = ClubCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            club = Club.objects.create(name=data["name"], slug=data["slug"])
            copy_default_xp_table(club)
            membership, temp = get_or_create_member(
                club,
                data["admin_email"],
                data["admin_display_name"],
                is_club_admin=True,
            )
        context = {"club": club, "membership": membership}
        if temp is not None:
            context["temp_password"] = temp
            context["temp_user"] = membership.user
        response = render(request, "accounts/clubs/created.html", context)
        response["Cache-Control"] = "no-store"
        return response
    return render(request, "accounts/clubs/new.html", {"form": form})
