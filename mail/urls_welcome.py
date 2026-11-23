"""Welcome email URL patterns."""

from django.urls import path

from mail.views import welcome

# Club URLs (mounted at c/<club_slug>/mail/, namespace 'mail')
club_urlpatterns = [
    path("welcome/resend/", welcome.welcome_resend, name="welcome_resend"),
    path(
        "welcome/show-link/<int:message_pk>/",
        welcome.welcome_show_link,
        name="welcome_show_link",
    ),
]

# Public URLs (mounted at /mail/, namespace 'mail_public')
public_urlpatterns = [
    path("welcome/<str:token>/", welcome.welcome_set_password, name="welcome_set_password"),
]
