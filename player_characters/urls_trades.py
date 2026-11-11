from django.urls import path

from .views import trades

app_name = "trades"
urlpatterns = [
    path("", trades.index, name="index"),
]
