"""Forgot password and password reset URL patterns."""

from django.urls import path

from mail.views import forgot_password

# No club URLs for password reset - it's a public flow

# Public URLs (mounted at /mail/, namespace 'mail_public')
public_urlpatterns = [
    path("forgot/", forgot_password.forgot_password, name="forgot_password"),
    path("reset/<str:token>/", forgot_password.reset_password, name="reset_password"),
]
