from django.apps import AppConfig


class ItemsConfig(AppConfig):
    name = "items"

    def ready(self):
        from accounts import navigation

        reg = navigation.register
        reg("items", "Items", "items:index", None, 10, icon="box-seam")
