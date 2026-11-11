from django.http import HttpResponse
from django.views.decorators.http import require_POST

from accounts.permissions import club_member_required

# Stubs: filled by the "Accept, decline and cancel a trade" story.


@club_member_required
@require_POST
def accept(request, club_slug, pk):
    return HttpResponse(status=501)


@club_member_required
@require_POST
def decline(request, club_slug, pk):
    return HttpResponse(status=501)


@club_member_required
@require_POST
def cancel(request, club_slug, pk):
    return HttpResponse(status=501)
