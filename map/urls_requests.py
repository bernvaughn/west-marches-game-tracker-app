from django.urls import path

from .views import requests as views

urlpatterns = [
    path("requests/", views.queue, name="requests"),
    path("requests/new/visit/<int:map_id>/", views.visit_new, name="request_visit"),
    path(
        "requests/new/<str:kind>/location/<int:location_id>/",
        views.credit_new,
        name="request_credit",
    ),
    path("requests/<int:pk>/approve/", views.approve, name="request_approve"),
    path("requests/<int:pk>/decline/", views.decline, name="request_decline"),
]
