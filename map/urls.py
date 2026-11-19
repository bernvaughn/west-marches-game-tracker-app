from django.urls import path, register_converter

from .converters import SignedIntConverter
from .views import core, credit, edit, requests, views, xp

register_converter(SignedIntConverter, "signed")

app_name = "map"
urlpatterns = [
    # core
    path("", core.IndexView.as_view(), name="index"),
    path("<int:map_id>/", core.DetailView.as_view(), name="detail"),
    path("<int:map_id>/tile/<signed:q>/<signed:r>/", core.TileView.as_view(), name="tile"),
    # edit
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
    # xp
    path("xp/", xp.xp_table, name="xp"),
    # credit
    path("<int:map_id>/tile/<signed:q>/<signed:r>/visits/", credit.visits, name="visits"),
    path("location/<int:pk>/found/", credit.found, name="found"),
    path("location/<int:pk>/credit/<str:kind>/", credit.credit, name="credit"),
    # requests
    path("requests/", requests.queue, name="requests"),
    path("requests/new/visit/<int:map_id>/", requests.visit_new, name="request_visit"),
    path(
        "requests/new/<str:kind>/location/<int:location_id>/",
        requests.credit_new,
        name="request_credit",
    ),
    path("requests/<int:pk>/approve/", requests.approve, name="request_approve"),
    path("requests/<int:pk>/decline/", requests.decline, name="request_decline"),
    path("requests/bulk-approve/", requests.bulk_approve, name="request_bulk_approve"),
    # views
    path("<int:map_id>/print/", views.print_map, name="print"),
]
