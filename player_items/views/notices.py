"""Views for player notices (U163)."""

from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from accounts.htmx import is_htmx
from accounts.permissions import club_member_required

from ..models import PlayerNotice


@club_member_required
def dismiss_notice(request, club_slug, pk):
    """POST: dismiss a PlayerNotice owned by the current membership.

    Only the notice's own membership may dismiss it. HTMX requests get an
    empty 204 so the calling page can swap the notice row out; other
    requests redirect to the dashboard.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    notice = get_object_or_404(PlayerNotice.objects.for_club(request.club), pk=pk)
    if notice.membership_id != request.membership.id:
        return HttpResponseForbidden("You can only dismiss your own notices.")

    notice.dismiss()

    if is_htmx(request):
        return HttpResponse(status=204)
    return redirect(reverse("accounts:player_dashboard", args=[request.club.slug]))
