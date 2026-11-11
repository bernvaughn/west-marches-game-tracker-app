from django.urls import path

from .views import manage, play

app_name = "quests"
urlpatterns = [
    path("", play.index, name="index"),
    path("<int:pk>/", play.detail, name="detail"),
    path("<int:pk>/turn-in/", play.turn_in, name="turn_in"),
    path("manage/", manage.quest_list, name="manage"),
    path("manage/new/", manage.quest_create, name="create"),
    path("manage/<int:pk>/edit/", manage.quest_edit, name="edit"),
    path("manage/<int:pk>/delete/", manage.quest_delete, name="delete"),
]
