from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from ..models import Membership
from ..passwords import set_temporary_password
from ..permissions import can_reset_password, club_admin_required
from ..scoping import club_get_object_or_404


class ClearFlagPasswordChangeView(PasswordChangeView):
    """Change the password, clear the forced-change flag, stay signed in."""

    def form_valid(self, form):
        form.user.must_change_password = False
        # form.save() saves the user; the base view then refreshes the session hash.
        return super().form_valid(form)


password_change = login_required(ClearFlagPasswordChangeView.as_view())


@club_admin_required
def reset_password(request, club_slug, membership_id):
    membership = club_get_object_or_404(request, Membership, pk=membership_id)
    if not can_reset_password(request.user, membership.user):
        raise PermissionDenied
    if request.method == "POST":
        temp = set_temporary_password(membership.user)
        response = render(
            request,
            "accounts/passwords/reset_done.html",
            {"temp_password": temp, "temp_user": membership.user},
        )
        response["Cache-Control"] = "no-store"
        return response
    return render(request, "accounts/passwords/reset_confirm.html", {"target": membership.user})
