from django.urls import path

from .views import characters

app_name = "characters"
urlpatterns = [
    path("", characters.index, name="index"),
]
