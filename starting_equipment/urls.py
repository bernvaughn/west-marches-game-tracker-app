from django.urls import include, path

app_name = "starting_equipment"

urlpatterns = [
    path("templates/", include("starting_equipment.urls_templates")),
    path("templates/<int:template_pk>/", include("starting_equipment.urls_entries")),
    path("", include("starting_equipment.urls_requests")),
]
