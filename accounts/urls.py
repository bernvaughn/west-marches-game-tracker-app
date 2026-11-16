from django.urls import path

from .views import dashboard, dashboard_downtime, dashboard_quick_actions, inbox, passwords, people

app_name = "accounts"
urlpatterns = [
    path("", people.member_list, name="index"),
    path("dashboard/", dashboard.player_dashboard, name="player_dashboard"),
    path(
        "dashboard/partial/quick_action_sell_junk/",
        dashboard_quick_actions.quick_action_sell_junk,
        name="quick_action_sell_junk",
    ),
    path(
        "dashboard/partial/quick_action_buy_potions/",
        dashboard_quick_actions.quick_action_buy_potions,
        name="quick_action_buy_potions",
    ),
    path(
        "dashboard/partial/downtime_spend/<int:action_pk>/",
        dashboard_downtime.downtime_spend_partial,
        name="dashboard_downtime_spend",
    ),
    path(
        "dashboard/partial/<str:provider_key>/",
        dashboard.dashboard_partial,
        name="dashboard_partial",
    ),
    path(
        "characters/<int:pk>/preview/",
        dashboard.character_preview,
        name="character_preview",
    ),
    path(
        "characters/<int:pk>/print-session-pack-modal/",
        dashboard.print_session_pack_modal,
        name="print_session_pack_modal",
    ),
    path("whitelist/", people.whitelist, name="whitelist"),
    path(
        "members/<int:membership_id>/reset-password/",
        passwords.reset_password,
        name="reset_password",
    ),
    path("messages/new/", inbox.message_new, name="message_new"),
    path("messages/stock/new/", inbox.stock_request_new, name="stock_request_new"),
    path("messages/", inbox.message_inbox, name="message_inbox"),
    path("messages/<int:pk>/status/", inbox.message_status, name="message_status"),
    path(
        "messages/<int:pk>/status/<slug:status>/confirm/",
        inbox.message_status_confirm,
        name="message_status_confirm",
    ),
    path(
        "messages/<int:pk>/give/coins/",
        inbox.message_give,
        {"kind": "coins"},
        name="message_give_coins",
    ),
    path(
        "messages/<int:pk>/give/items/",
        inbox.message_give,
        {"kind": "items"},
        name="message_give_items",
    ),
    path(
        "messages/<int:pk>/give/map/",
        inbox.message_give,
        {"kind": "map"},
        name="message_give_map",
    ),
]