from django.urls import path

from .views import views

urlpatterns = [
    path("<int:map_id>/print/", views.print_map, name="print"),
]
