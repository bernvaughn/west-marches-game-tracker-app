from django.urls import path

from . import views
from .views import review

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
    path("review/", review.review, name="review"),
    path("review/confirm/", review.leave_as_is_confirm, name="leave_as_is_confirm"),
    path("review/leave-as-is/", review.leave_as_is, name="leave_as_is"),
]
