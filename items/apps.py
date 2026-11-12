from django.apps import AppConfig


class ItemsConfig(AppConfig):
    name = "items"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin, not_admin

        reg = navigation.register
        reg("more", "Items", "items:index", not_admin, 110)
        reg("admin", "Item catalogue", "items:index", is_admin, 40)
