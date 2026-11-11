from django.urls import path

from .views import xp as views

urlpatterns = [
    path("xp/", views.xp_table, name="xp"),
]
