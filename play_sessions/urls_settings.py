"""URL patterns for session settings."""

from django.urls import path

from .views import settings

urlpatterns = [
    path("settings/", settings.session_settings, name="settings"),
]
