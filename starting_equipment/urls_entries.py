from django.urls import path

from .views import entries as entry_views

urlpatterns = [
    # Class entries
    path("class/", entry_views.ClassEntryListView.as_view(), name="class_entry_list"),
    path("class/new/", entry_views.ClassEntryCreateView.as_view(), name="class_entry_create"),
    path("class/<int:pk>/edit/", entry_views.ClassEntryEditView.as_view(), name="class_entry_edit"),
    path(
        "class/<int:pk>/delete/",
        entry_views.ClassEntryDeleteView.as_view(),
        name="class_entry_delete",
    ),
    # Background entries
    path(
        "background/", entry_views.BackgroundEntryListView.as_view(), name="background_entry_list"
    ),
    path(
        "background/new/",
        entry_views.BackgroundEntryCreateView.as_view(),
        name="background_entry_create",
    ),
    path(
        "background/<int:pk>/edit/",
        entry_views.BackgroundEntryEditView.as_view(),
        name="background_entry_edit",
    ),
    path(
        "background/<int:pk>/delete/",
        entry_views.BackgroundEntryDeleteView.as_view(),
        name="background_entry_delete",
    ),
    # Level coins
    path("level-coins/", entry_views.LevelCoinsListView.as_view(), name="level_coins_list"),
    path("level-coins/new/", entry_views.LevelCoinsCreateView.as_view(), name="level_coins_create"),
    path(
        "level-coins/<int:pk>/edit/",
        entry_views.LevelCoinsEditView.as_view(),
        name="level_coins_edit",
    ),
    path(
        "level-coins/<int:pk>/delete/",
        entry_views.LevelCoinsDeleteView.as_view(),
        name="level_coins_delete",
    ),
    # Magic options
    path("magic-options/", entry_views.MagicOptionListView.as_view(), name="magic_option_list"),
    path(
        "magic-options/new/",
        entry_views.MagicOptionCreateView.as_view(),
        name="magic_option_create",
    ),
    path(
        "magic-options/<int:pk>/edit/",
        entry_views.MagicOptionEditView.as_view(),
        name="magic_option_edit",
    ),
    path(
        "magic-options/<int:pk>/delete/",
        entry_views.MagicOptionDeleteView.as_view(),
        name="magic_option_delete",
    ),
]
