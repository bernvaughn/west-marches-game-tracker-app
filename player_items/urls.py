from django.urls import path

from . import views
from .views import merge, promote, review

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
    path("review/<str:name_key>/promote/", promote.promote, name="promote"),
    path("review/merge/", merge.merge_form, name="merge_form"),
    path("review/merge/confirm/", merge.merge_confirm, name="merge_confirm"),
    path("suggest/", merge.suggest_matches_view, name="suggest"),
    path(
        "notices/<int:pk>/dismiss/",
        views.dismiss_notice,
        name="dismiss_notice",
    ),
]
