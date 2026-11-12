from django.urls import path

from .views import inbox, passwords, people

app_name = "accounts"
urlpatterns = [
    path("", people.member_list, name="index"),
    path("whitelist/", people.whitelist, name="whitelist"),
    path(
        "members/<int:membership_id>/reset-password/",
        passwords.reset_password,
        name="reset_password",
    ),
    path("messages/new/", inbox.message_new, name="message_new"),
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
