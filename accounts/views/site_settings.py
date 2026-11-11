from django.shortcuts import render

from ..permissions import site_admin_required


@site_admin_required
def site_settings(request):
    return render(request, "accounts/stub.html", {"title": "Site settings"})
