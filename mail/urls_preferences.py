"""Email preferences URL patterns (E8/M9)."""

from django.urls import path

from mail.views import preferences

# Club URLs (mounted at c/<club_slug>/mail/, namespace 'mail')
club_urlpatterns = [
    path("preferences/", preferences.preferences, name="preferences"),
]

# Public URLs (mounted at /mail/, namespace 'mail_public')
public_urlpatterns = [
    path("unsubscribe/<str:token>/", preferences.unsubscribe, name="unsubscribe"),
]
