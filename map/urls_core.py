from django.urls import path

from .views import core

urlpatterns = [
    path("", core.index, name="index"),
    path("<int:map_id>/", core.detail, name="detail"),
    path("<int:map_id>/tile/<signed:q>/<signed:r>/", core.tile, name="tile"),
]
