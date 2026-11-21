"""Stub views for character archive actions (C1)."""

from django.http import Http404
from django.utils.decorators import method_decorator
from django.views import View

from accounts.permissions import club_member_required


@method_decorator(club_member_required, name="dispatch")
class ArchiveView(View):
    def get(self, request, club_slug, pk):
        raise Http404


@method_decorator(club_member_required, name="dispatch")
class UnarchiveView(View):
    def get(self, request, club_slug, pk):
        raise Http404
