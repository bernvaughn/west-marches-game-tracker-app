from django.urls import path

from .views import core

urlpatterns = [
    path("", core.IndexView.as_view(), name="index"),
    path("<int:map_id>/", core.DetailView.as_view(), name="detail"),
    path("<int:map_id>/tile/<signed:q>/<signed:r>/", core.TileView.as_view(), name="tile"),
]
