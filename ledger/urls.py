from django.urls import path

from . import views

app_name = "ledger"
urlpatterns = [
    path("", views.index, name="index"),
    path("character/<int:pk>/", views.character_history, name="character_history"),
]
