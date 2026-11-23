"""URL patterns for reminder settings (E5)."""

from django.urls import path

from mail.views.reminder_settings import reminder_settings

club_urlpatterns = [
    path("reminders/", reminder_settings, name="reminder_settings"),
]

# No public URLs for reminders
public_urlpatterns = []
