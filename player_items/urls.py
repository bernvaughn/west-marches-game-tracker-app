from django.urls import path

from . import views

app_name = "player_items"

urlpatterns = [
    path(
        "<int:character_pk>/entries/add/",
        views.add_entry,
        name="add",
    ),
    path(
        "<int:character_pk>/entries/<int:pk>/edit/",
        views.edit_entry,
        name="edit",
    ),
    path(
        "<int:character_pk>/entries/<int:pk>/remove/",
        views.remove_entry,
        name="remove",
    ),
]
