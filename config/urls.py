from django.contrib import admin
from django.urls import include, path

from accounts import views as account_views
from config import views as config_views
from play_sessions.urls import public_urlpatterns as play_sessions_public_urlpatterns

club_patterns = [
    path("", account_views.club_home, name="club_home"),
    path("accounts/", include("accounts.urls")),
    path("characters/", include("player_characters.urls_characters")),
    path("items/", include("items.urls")),
    path("shops/", include("shops.urls")),
    path("ledger/", include("ledger.urls")),
    path("map/", include("map.urls")),
    path("quests/", include("quests.urls")),
    path("downtime/", include("downtime.urls")),
    path("starting-equipment/", include("starting_equipment.urls")),
    path("options/", include("character_options.urls")),
    path("agent/", include("agent_access.urls")),
    path("sessions/", include("play_sessions.urls")),
]

urlpatterns = [
    path("favicon.ico", config_views.favicon, name="favicon"),
    path("healthz", config_views.healthz, name="healthz"),
    path("", account_views.home, name="home"),
    path("", include("accounts.urls_site")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("", include("agent_access.urls_root")),
    path("sessions/", include((play_sessions_public_urlpatterns, "play_sessions_public"))),
    path("c/<slug:club_slug>/", include(club_patterns)),
]
