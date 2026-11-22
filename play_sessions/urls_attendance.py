"""URL patterns for attendance feature (P5, P6)."""

from django.urls import path

from .views.attendance import attendance, rsvp_for

urlpatterns = [
    path("<int:pk>/attendance/", attendance, name="attendance"),
    path("<int:pk>/rsvp-for/", rsvp_for, name="rsvp_for"),
]
