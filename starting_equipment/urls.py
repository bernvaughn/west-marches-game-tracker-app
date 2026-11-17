from django.urls import path

from . import views

app_name = "starting_equipment"

urlpatterns = [
    path("templates/", views.StartingEquipmentPlaceholderView.as_view(), name="templates"),
]