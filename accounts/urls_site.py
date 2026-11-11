from django.urls import path

from .views import clubs, passwords, site_settings

urlpatterns = [
    path("accounts/password_change/", passwords.password_change, name="password_change"),
    path("site/clubs/", clubs.club_list, name="site_clubs"),
    path("site/clubs/new/", clubs.club_new, name="site_club_new"),
    path("site/settings/", site_settings.site_settings, name="site_settings"),
]
