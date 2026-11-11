from django.http import HttpResponse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.permissions import club_member_required

# Stubs: filled by the "Edit sides, approve and complete a trade" story.


@club_member_required
@require_http_methods(["GET", "POST"])
def edit_side(request, club_slug, pk):
    return HttpResponse(status=501)


@club_member_required
@require_POST
def approve(request, club_slug, pk):
    return HttpResponse(status=501)
