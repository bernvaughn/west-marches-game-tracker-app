from django.urls import path

from .mcp.server import mcp_view

urlpatterns = [
    path("mcp", mcp_view, name="mcp"),
]
