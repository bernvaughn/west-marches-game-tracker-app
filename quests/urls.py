from django.urls import path

from . import views

app_name = "quests"
urlpatterns = [
    path("", views.index, name="index"),
]
