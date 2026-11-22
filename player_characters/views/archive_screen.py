"""View for the archived characters screen (U145)."""

from django.shortcuts import render
from django.urls import reverse

from accounts.models import Membership
from accounts.permissions import club_member_required, is_club_admin, is_game_master
from player_characters.models import Character


@club_member_required
def archived(request, club_slug):
    """List archived characters for this club.

    Players see only their own. GMs and club admins see all with owner names
    and an owner filter.
    """
    user = request.user
    club = request.club
    sees_all = is_club_admin(user, club) or is_game_master(user, club)

    qs = (
        Character.objects.filter(club=club, archived_at__isnull=False)
        .select_related("owner__user")
        .order_by("-archived_at", "name")
    )

    if not sees_all:
        qs = qs.filter(owner=request.membership)

    owner_choices = None
    selected_owner = None
    if sees_all:
        # Distinct owners among the archived rows (before filtering).
        owner_pks = set(qs.values_list("owner_id", flat=True).distinct())
        owner_choices = []
        owners = (
            Membership.objects.filter(pk__in=owner_pks)
            .select_related("user")
            .order_by("user__display_name")
        )
        for m in owners:
            owner_choices.append({"pk": m.pk, "name": m.user.display_name})

        raw_owner = request.GET.get("owner")
        if raw_owner is not None:
            try:
                selected_owner = int(raw_owner)
            except (TypeError, ValueError):
                selected_owner = None
            else:
                if selected_owner not in owner_pks:
                    selected_owner = None
                else:
                    qs = qs.filter(owner_id=selected_owner)

    characters = []
    for c in qs:
        characters.append(
            {
                "character": c,
                "detail_url": reverse("characters:detail", args=[club.slug, c.pk]),
            }
        )

    return render(
        request,
        "player_characters/characters/archived.html",
        {
            "characters": characters,
            "sees_all": sees_all,
            "owner_choices": owner_choices,
            "selected_owner": selected_owner,
        },
    )
