"""View for the fallen characters page (U147).

Lists every dead character in the club, archived ones included, ordered by
death date newest first. Any club member can open it.
"""

from django.shortcuts import render
from django.urls import reverse

from accounts.permissions import club_member_required
from player_characters.models import Character


@club_member_required
def fallen(request, club_slug):
    """List dead characters for this club, newest death first."""
    club = request.club

    qs = (
        Character.objects.filter(club=club, died_on__isnull=False)
        .select_related("owner__user")
        .order_by("-died_on", "name")
    )

    characters = [
        {"character": c, "detail_url": reverse("characters:detail", args=[club.slug, c.pk])}
        for c in qs
    ]

    return render(
        request,
        "player_characters/characters/fallen.html",
        {"characters": characters},
    )
