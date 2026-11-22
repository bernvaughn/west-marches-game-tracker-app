from django.db import transaction
from django.db.models import Count
from django.shortcuts import render

from ..club_seeding import seed_new_club
from ..forms.clubs import ClubCreateForm
from ..models import Club, User
from ..passwords import get_or_create_member
from ..permissions import site_admin_required
from mail.models import ClubMailSettings


@site_admin_required
def club_list(request):
    clubs = Club.objects.annotate(member_count=Count("memberships")).order_by("name")
    return render(request, "accounts/clubs/list.html", {"clubs": clubs})


@site_admin_required
def club_new(request):
    form = ClubCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        existing = User.objects.filter(email__iexact=data["admin_email"]).first()
        if existing and not data["confirm_existing"]:
            # Tell the site admin first. Resubmitting the same form confirms it.
            posted = request.POST.copy()
            posted["confirm_existing"] = "1"
            form = ClubCreateForm(posted)
            return render(
                request,
                "accounts/clubs/new.html",
                {"form": form, "existing_user": existing},
            )
        with transaction.atomic():
            club = Club.objects.create(
                name=data["name"], slug=data["slug"], timezone=data["timezone"]
            )
            seed_new_club(club)
            contact_email = data.get("contact_email", "").strip().lower()
            ClubMailSettings.objects.create(club=club, contact_email=contact_email)
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
