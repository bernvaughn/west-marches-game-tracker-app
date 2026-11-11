from django.urls import include, path, register_converter

from .converters import SignedIntConverter

register_converter(SignedIntConverter, "signed")

app_name = "map"
urlpatterns = [
    path("", include("map.urls_core")),
    path("", include("map.urls_edit")),
    path("", include("map.urls_xp")),
    path("", include("map.urls_credit")),
    path("", include("map.urls_requests")),
    path("", include("map.urls_views")),
]
