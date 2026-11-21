"""Stub view for the fallen characters page (C1). A later story replaces the body."""

from django.http import Http404

from accounts.permissions import club_member_required


@club_member_required
def fallen(request, club_slug):
    raise Http404
