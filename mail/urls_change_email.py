"""URL patterns for email change (E9)."""

from django.urls import path

from .views.change_email import ConfirmEmailView, change_email

club_urlpatterns = [
    path("change-email/", change_email, name="change_email"),
]

public_urlpatterns = [
    path("email/confirm/<str:token>/", ConfirmEmailView.as_view(), name="confirm_email"),
]
