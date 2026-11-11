from django.shortcuts import render

from ..permissions import site_admin_required


@site_admin_required
def club_list(request):
    return render(request, "accounts/stub.html", {"title": "Clubs"})


@site_admin_required
def club_new(request):
    return render(request, "accounts/stub.html", {"title": "New club"})
