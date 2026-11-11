from django.urls import path

from .views import connections

urlpatterns = [
    path("", connections.connection_list, name="connections"),
    path("<int:pk>/revoke/", connections.connection_revoke, name="connection_revoke"),
]
