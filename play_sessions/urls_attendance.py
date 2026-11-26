"""URL patterns for attendance feature (P5, P6, P14, P15)."""

from django.urls import path

from .views.attendance import attendance, bringing, rsvp_for

urlpatterns = [
    path("<int:pk>/attendance/", attendance, name="attendance"),
    path("<int:pk>/rsvp-for/", rsvp_for, name="rsvp_for"),
    path("<int:pk>/bringing/", bringing, name="bringing"),
]
