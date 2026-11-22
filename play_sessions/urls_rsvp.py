"""URL patterns for RSVP (P4)."""

from django.urls import path

from .views import rsvp

urlpatterns = [
    path("<int:pk>/rsvp/", rsvp.rsvp_set, name="rsvp_set"),
]
