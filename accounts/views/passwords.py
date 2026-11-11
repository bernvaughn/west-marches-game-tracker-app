from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.shortcuts import render

from ..permissions import club_admin_required

password_change = login_required(PasswordChangeView.as_view())


@club_admin_required
def reset_password(request, club_slug, membership_id):
    return render(request, "accounts/stub.html", {"title": "Reset password"})
