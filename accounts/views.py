from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .context_processors import clubs as clubs_context
from .permissions import club_member_required


@login_required
def home(request):
    return render(request, "home.html", clubs_context(request))


@club_member_required
def club_home(request, club_slug):
    return render(request, "club_home.html")


@club_member_required
def index(request, club_slug):
    return render(request, "accounts/index.html")
