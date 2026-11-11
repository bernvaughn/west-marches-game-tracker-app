from django.urls import include, path

from .oauth.views import mcp_entry

urlpatterns = [
    path("", include("agent_access.oauth.urls")),
    path("mcp", mcp_entry, name="mcp"),
]
