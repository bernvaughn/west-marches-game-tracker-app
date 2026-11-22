"""Public URL patterns for email RSVP (E6)."""

from django.urls import path

from .views.email_rsvp import EmailRSVPView

public_urlpatterns = [
    path("rsvp/<str:token>/", EmailRSVPView.as_view(), name="email_rsvp"),
]

# No club_urlpatterns for RSVP - it's a public page only
