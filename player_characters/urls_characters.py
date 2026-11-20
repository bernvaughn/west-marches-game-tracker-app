from django.urls import path

from .views import (
    character_adjust,
    character_consume,
    character_junk,
    character_notes,
    character_open,
    character_print,
    character_shop,
    character_slips,
    characters,
    selection,
)

app_name = "characters"
urlpatterns = [
    path("", characters.IndexView.as_view(), name="index"),
    path("mine/", characters.MineView.as_view(), name="mine"),
    path("directory/", characters.DirectoryView.as_view(), name="directory"),
    path("new/", characters.CreateView.as_view(), name="create"),
    path("select/", selection.select, name="select"),
    path("slips/", character_slips.slips, name="slips"),
    path("slips/print/", character_slips.slips_print, name="slips_print"),
    path("<int:pk>/", characters.DetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", characters.EditView.as_view(), name="edit"),
    path("<int:pk>/handover/", characters.HandoverView.as_view(), name="handover"),
    path("<int:pk>/adjust/", character_adjust.adjust, name="adjust"),
    path("<int:pk>/consume/", character_adjust.consume, name="consume"),
    path("<int:pk>/print/", character_print.print_items, name="print_items"),
    path("<int:pk>/items/<int:item_pk>/print/", character_print.print_item, name="print_item"),
    path("<int:pk>/shop/", character_shop.shop_toggle, name="shop_toggle"),
    path(
        "<int:pk>/items/<int:item_pk>/consume/",
        character_consume.player_consume,
        name="player_consume",
    ),
    path("<int:pk>/items/<int:item_pk>/junk/", character_junk.junk, name="junk"),
    path("<int:pk>/items/<int:item_pk>/note/", character_notes.note, name="note"),
    path(
        "<int:pk>/items/<int:item_pk>/open/",
        character_open.open_container_view,
        name="open_container",
    ),
    path(
        "<int:pk>/print-session-pack/",
        character_print.print_session_pack,
        name="print_session_pack",
    ),
    path("<int:pk>/preview/", selection.character_preview, name="preview"),
    path("bulk-award/", character_adjust.bulk_award, name="bulk_award"),
]
