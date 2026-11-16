from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from ..models import Membership
from ..passwords import save_password_history, set_temporary_password
from ..permissions import can_reset_password, club_admin_required
from ..scoping import club_get_object_or_404
from ..ratelimit import RateLimitMixin, rate_limit


class ClearFlagPasswordChangeView(RateLimitMixin, PasswordChangeView):
    """Change the password, clear the forced-change flag, stay signed in."""

    ratelimit_prefix = "password_change"
    ratelimit_limit = settings.RATELIMIT_PASSWORD_ATTEMPTS
    ratelimit_window = settings.RATELIMIT_PASSWORD_WINDOW

    def form_valid(self, form):
        form.user.must_change_password = False
        # form.save() saves the user; the base view then refreshes the session hash.
        response = super().form_valid(form)
        save_password_history(form.user, form.cleaned_data["new_password1"])
        return response

    def dispatch(self, request, *args, **kwargs):
        # Use user ID as the rate limit key for authenticated users
        self.ratelimit_key_func = lambda req: str(req.user.id) if req.user.is_authenticated else "anonymous"
        return super().dispatch(request, *args, **kwargs)


password_change = login_required(ClearFlagPasswordChangeView.as_view())


@club_admin_required
@rate_limit(
    prefix="password_reset",
    limit=settings.RATELIMIT_PASSWORD_ATTEMPTS,
    window=settings.RATELIMIT_PASSWORD_WINDOW,
    key_func=lambda req, club_slug, membership_id: str(membership_id),
)
def reset_password(request, club_slug, membership_id):
    membership = club_get_object_or_404(request, Membership, pk=membership_id)
    if not can_reset_password(request.user, membership.user):
        raise PermissionDenied
    if request.method == "POST":
        temp = set_temporary_password(membership.user)
        save_password_history(membership.user, temp)
        response = render(
            request,
            "accounts/passwords/reset_done.html",
            {"temp_password": temp, "temp_user": membership.user},
        )
        response["Cache-Control"] = "no-store"
        return response
    return render(request, "accounts/passwords/reset_confirm.html", {"target": membership.user})
