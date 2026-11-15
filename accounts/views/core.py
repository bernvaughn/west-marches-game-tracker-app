from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render

from player_characters.models import Character

from ..context_processors import clubs as clubs_context
from ..models import Membership
from ..permissions import club_member_required, is_club_admin, is_game_master


@login_required
def home(request):
    ctx = clubs_context(request)
    clubs = list(ctx["user_clubs"])
    ids = [c.id for c in clubs]
    mine, gms, players, chars = {}, {}, {}, {}
    if ids:
        for m in Membership.objects.filter(user=request.user, club_id__in=ids):
            mine[m.club_id] = m
        gm_qs = (
            Membership.objects.filter(club_id__in=ids, is_game_master=True)
            .select_related("user")
            .order_by("user__display_name")
        )
        for m in gm_qs:
            gms.setdefault(m.club_id, []).append(m.user.display_name or "Unnamed game master")
        counts = (
            Membership.objects.filter(club_id__in=ids, is_game_master=False, is_club_admin=False)
            .values("club_id")
            .annotate(n=Count("id"))
        )
        players = {r["club_id"]: r["n"] for r in counts}
        char_qs = (
            Character.objects.filter(owner__user=request.user, club_id__in=ids)
            .only("id", "name", "club_id")
            .order_by("name")
        )
        for ch in char_qs:
            chars.setdefault(ch.club_id, []).append(ch.name)
    cards = []
    for club in clubs:
        m = mine.get(club.id)
        roles = []
        if m:
            if m.is_club_admin:
                roles.append("Club admin")
            if m.is_game_master:
                roles.append("Game master")
            if not roles:
                roles.append("Player")
        cards.append(
            {
                "club": club,
                "roles": roles,
                "gms": gms.get(club.id, []),
                "players": players.get(club.id, 0),
                "characters": chars.get(club.id, []),
            }
        )
    ctx["cards"] = cards
    return render(request, "home.html", ctx)


@club_member_required
def club_home(request, club_slug):
    club = request.club
    # Players go to dashboard, GMs/admins see navigation cards
    if not is_game_master(request.user, club) and not is_club_admin(request.user, club):
        return redirect("accounts:player_dashboard", club_slug=club.slug)
    return render(request, "club_home.html")
