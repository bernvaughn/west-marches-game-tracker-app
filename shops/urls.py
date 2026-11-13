from django.urls import path

from .views import browse, buy, manage, player_shop, rotations, sell, sell_junk

app_name = "shops"
urlpatterns = [
    path("", browse.index, name="index"),
    path("<int:shop_id>/", browse.shop_detail, name="detail"),
    path("<int:shop_id>/stock/", browse.stock_fragment, name="stock_fragment"),
    path("<int:shop_id>/buy/<int:stock_id>/", buy.buy, name="buy"),
    path("<int:shop_id>/sell/<int:item_id>/", sell.sell_item, name="sell_item"),
    path("<int:shop_id>/sell-junk/", sell_junk.sell_junk, name="sell_junk"),
    path("stall/<int:character_id>/", player_shop.player_shop, name="player_shop"),
    path(
        "stall/<int:character_id>/buy/<int:item_id>/",
        player_shop.buy,
        name="player_shop_buy",
    ),
    path("manage/", manage.shop_list, name="manage_list"),
    path("manage/street/", manage.street_settings, name="street_settings"),
    path("manage/new/", manage.shop_create, name="manage_create"),
    path("manage/<int:shop_id>/", manage.shop_edit, name="manage_edit"),
    path("manage/<int:shop_id>/stock/new/", manage.stock_add, name="stock_add"),
    path("manage/<int:shop_id>/stock/<int:stock_id>/", manage.stock_edit, name="stock_edit"),
    path(
        "manage/<int:shop_id>/stock/<int:stock_id>/remove/",
        manage.stock_remove,
        name="stock_remove",
    ),
    path("rotations/", rotations.rotation_list, name="rotation_list"),
    path("rotations/new/", rotations.rotation_create, name="rotation_create"),
    path("rotations/<int:rotation_id>/", rotations.rotation_edit, name="rotation_edit"),
    path(
        "rotations/<int:rotation_id>/delete/",
        rotations.rotation_delete,
        name="rotation_delete",
    ),
]
