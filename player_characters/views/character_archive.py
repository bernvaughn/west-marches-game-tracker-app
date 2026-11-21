"""Stub views for character archive actions (C1). Later stories replace the bodies."""

from django.http import Http404

from accounts.permissions import club_member_required


@club_member_required
def archive(request, club_slug, pk):
    raise Http404


@club_member_required
def unarchive(request, club_slug, pk):
    raise Http404
