"""URL patterns for the schedule feature."""

from django.urls import path

from .views import schedule

urlpatterns = [
    path("new/", schedule.session_create, name="session_create"),
    path("<int:pk>/edit/", schedule.session_edit, name="session_edit"),
    path("<int:pk>/cancel/", schedule.session_cancel, name="session_cancel"),
    path("<int:pk>/cancel-series/", schedule.series_cancel, name="series_cancel"),
]
