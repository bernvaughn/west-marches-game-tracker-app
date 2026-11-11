from django.urls import path

from . import views

app_name = "agent_access"
urlpatterns = [
    path("", views.index, name="index"),
]
