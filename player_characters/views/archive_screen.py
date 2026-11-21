"""Stub view for the archived characters screen (C1). A later story replaces the body."""

from django.http import Http404

from accounts.permissions import club_member_required


@club_member_required
def archived(request, club_slug):
    raise Http404
