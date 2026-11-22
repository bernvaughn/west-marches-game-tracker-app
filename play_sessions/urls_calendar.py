"""URLs for the session calendar feature.

Mounted by `config/urls.py`:
- club-scoped at ``c/<club_slug>/sessions/`` (namespace ``play_sessions``)
- public at ``/sessions/`` (namespace ``play_sessions_public``)
"""

from django.urls import path

from .views.calendar import calendar_page, feed_reset, public_feed

app_name = "play_sessions"

urlpatterns = [
    path("", calendar_page, name="calendar"),
    path("feed/reset/", feed_reset, name="feed_reset"),
]

public_urlpatterns = [
    path("feed/<slug:token>.ics", public_feed, name="feed"),
]
