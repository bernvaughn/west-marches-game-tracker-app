"""Club scoping helpers. Every club-owned model sets `club_path` and uses ClubScopedManager."""

from django.db import models
from django.shortcuts import get_object_or_404


class ClubScopedQuerySet(models.QuerySet):
    def for_club(self, club):
        return self.filter(**{self.model.club_path: club})


ClubScopedManager = models.Manager.from_queryset(ClubScopedQuerySet)


def club_queryset(request, model):
    return model.objects.for_club(request.club)


def club_get_object_or_404(request, model, **kwargs):
    return get_object_or_404(club_queryset(request, model), **kwargs)
