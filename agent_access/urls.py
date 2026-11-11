from django.urls import include, path

from . import urls_batches, urls_connections, urls_items, urls_reversal, views

app_name = "agent_access"
urlpatterns = [
    path("", views.index, name="index"),
    path("connections/", include(urls_connections)),
    path("batches/", include(urls_batches)),
    path("batches/", include(urls_reversal)),
    path("proposed-items/", include(urls_items)),
]
