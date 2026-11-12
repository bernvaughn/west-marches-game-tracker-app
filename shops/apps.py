from django.apps import AppConfig


class ShopsConfig(AppConfig):
    name = "shops"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin

        reg = navigation.register
        reg("town", "Shops", "shops:index", None, 20, icon="shop", shortcut_order=20)
        reg("admin", "Manage shops", "shops:manage_list", is_admin, 50)
        reg("admin", "Rotations", "shops:rotation_list", is_admin, 55)
