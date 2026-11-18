from django.urls import path

from starting_equipment.views import requests

urlpatterns = [
    path(
        "characters/<int:character_pk>/request/",
        requests.request_new,
        name="request_new",
    ),
    path(
        "requests/<int:pk>/decide/<slug:decision>/",
        requests.request_decide,
        name="request_decide",
    ),
    path(
        "requests/<int:pk>/decide/<slug:decision>/confirm/",
        requests.request_decide_confirm,
        name="request_decide_confirm",
    ),
    path(
        "requests/<int:pk>/status/",
        requests.request_status,
        name="request_status",
    ),
]
