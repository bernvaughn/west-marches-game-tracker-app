from django.apps import AppConfig


class StartingEquipmentConfig(AppConfig):
    name = "starting_equipment"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin

        reg = navigation.register
        reg(
            "items",
            "Starting Equipment Templates",
            "starting_equipment:templates",
            is_admin,
            54,
            icon="box",
        )
