from django.urls import path

from .views import credit

urlpatterns = [
    path("<int:map_id>/tile/<signed:q>/<signed:r>/visits/", credit.visits, name="visits"),
    path("location/<int:pk>/found/", credit.found, name="found"),
    path("location/<int:pk>/credit/<str:kind>/", credit.credit, name="credit"),
]
