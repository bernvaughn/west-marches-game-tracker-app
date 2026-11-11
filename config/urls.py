from django.contrib import admin
from django.urls import include, path

from accounts import views as account_views

club_patterns = [
    path("", account_views.club_home, name="club_home"),
    path("accounts/", include("accounts.urls")),
    path("characters/", include("player_characters.urls_characters")),
    path("trades/", include("player_characters.urls_trades")),
    path("items/", include("items.urls")),
    path("shops/", include("shops.urls")),
    path("ledger/", include("ledger.urls")),
    path("map/", include("map.urls")),
    path("quests/", include("quests.urls")),
    path("agent/", include("agent_access.urls")),
]

urlpatterns = [
    path("", account_views.home, name="home"),
    path("", include("accounts.urls_site")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("c/<slug:club_slug>/", include(club_patterns)),
]
