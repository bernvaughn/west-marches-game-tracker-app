from django.urls import path

from . import core
from .views import detail

app_name = "play_sessions"

urlpatterns = [
    path("<int:pk>/", detail.session_detail, name="session_detail"),
    *core.collect_urlpatterns("urlpatterns"),
]

public_urlpatterns = core.collect_urlpatterns("public_urlpatterns")