"""URL configuration for character_options admin."""

from django.urls import path

from character_options import views

app_name = "character_options"
urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:kind>/", views.list_options, name="list"),
    path("<slug:kind>/new/", views.create_option_view, name="create"),
    path("<slug:kind>/<int:pk>/edit/", views.edit_option, name="edit"),
    path("<slug:kind>/<int:pk>/archive/", views.archive_option, name="archive"),
    path("<slug:kind>/<int:pk>/restore/", views.restore_option, name="restore"),
    path("<slug:kind>/<int:pk>/delete/", views.delete_option, name="delete"),
    path("<slug:kind>/<int:pk>/move/", views.move_option_view, name="move"),
]
