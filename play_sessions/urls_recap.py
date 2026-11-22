"""URL patterns for the recap feature."""

from django.urls import path

from .views import recap

urlpatterns = [
    path("<int:pk>/recap/", recap.recap_edit, name="recap_edit"),
]
