from django.apps import AppConfig


class ShopsConfig(AppConfig):
    name = "shops"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin

        reg = navigation.register
        reg("items", "Shops", "shops:index", None, 20, icon="shop", shortcut_order=20)
        reg("items", "Manage shops", "shops:manage_list", is_admin, 50, icon="shop-window")
        reg("items", "Rotations", "shops:rotation_list", is_admin, 52, icon="arrow-repeat")
