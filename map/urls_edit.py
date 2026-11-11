from django.urls import path

from .views import edit

urlpatterns = [
    path("new/", edit.map_create, name="map_create"),
    path("<int:map_id>/edit/", edit.map_edit, name="map_edit"),
    path(
        "<int:map_id>/tile/<signed:q>/<signed:r>/locations/new/",
        edit.location_create,
        name="location_create",
    ),
    path("location/<int:pk>/edit/", edit.location_edit, name="location_edit"),
    path("location/<int:pk>/delete/", edit.location_delete, name="location_delete"),
    path("location/<int:pk>/encounters/new/", edit.encounter_create, name="encounter_create"),
    path("encounter/<int:pk>/edit/", edit.encounter_edit, name="encounter_edit"),
    path("encounter/<int:pk>/delete/", edit.encounter_delete, name="encounter_delete"),
]
