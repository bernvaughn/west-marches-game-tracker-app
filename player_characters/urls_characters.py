from django.urls import path

from .views import character_adjust, character_print, character_transfer, characters, selection

app_name = "characters"
urlpatterns = [
    path("", characters.index, name="index"),
    path("new/", characters.create, name="create"),
    path("select/", selection.select, name="select"),
    path("<int:pk>/", characters.detail, name="detail"),
    path("<int:pk>/edit/", characters.edit, name="edit"),
    path("<int:pk>/handover/", characters.handover, name="handover"),
    path("<int:pk>/adjust/", character_adjust.adjust, name="adjust"),
    path("<int:pk>/consume/", character_adjust.consume, name="consume"),
    path("<int:pk>/transfer/", character_transfer.transfer, name="transfer"),
    path("<int:pk>/print/", character_print.print_items, name="print_items"),
]
