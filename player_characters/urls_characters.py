from django.urls import path

from .views import (
    character_adjust,
    character_consume,
    character_junk,
    character_print,
    character_shop,
    character_slips,
    character_transfer,
    characters,
    selection,
)

app_name = "characters"
urlpatterns = [
    path("", characters.index, name="index"),
    path("mine/", characters.mine, name="mine"),
    path("directory/", characters.directory, name="directory"),
    path("new/", characters.create, name="create"),
    path("select/", selection.select, name="select"),
    path("transfer/", character_transfer.transfer_start, name="transfer_start"),
    path("slips/", character_slips.slips, name="slips"),
    path("slips/print/", character_slips.slips_print, name="slips_print"),
    path("<int:pk>/", characters.detail, name="detail"),
    path("<int:pk>/edit/", characters.edit, name="edit"),
    path("<int:pk>/handover/", characters.handover, name="handover"),
    path("<int:pk>/adjust/", character_adjust.adjust, name="adjust"),
    path("<int:pk>/consume/", character_adjust.consume, name="consume"),
    path("<int:pk>/transfer/", character_transfer.transfer, name="transfer"),
    path("<int:pk>/print/", character_print.print_items, name="print_items"),
    path("<int:pk>/items/<int:item_pk>/print/", character_print.print_item, name="print_item"),
    path("<int:pk>/shop/", character_shop.shop_toggle, name="shop_toggle"),
    path(
        "<int:pk>/items/<int:item_pk>/consume/",
        character_consume.player_consume,
        name="player_consume",
    ),
    path("<int:pk>/items/<int:item_pk>/junk/", character_junk.junk, name="junk"),
]
