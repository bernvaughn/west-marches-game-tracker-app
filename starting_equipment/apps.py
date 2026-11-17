from django.apps import AppConfig


class StartingEquipmentConfig(AppConfig):
    name = "starting_equipment"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin, not_admin

        reg = navigation.register
        reg("club", "Starting Equipment", "starting_equipment:templates", not_admin, 115)
        reg("admin", "Starting Equipment Templates", "starting_equipment:templates", is_admin, 45)