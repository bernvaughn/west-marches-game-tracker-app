from django.apps import AppConfig


class QuestsConfig(AppConfig):
    name = "quests"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin

        reg = navigation.register
        reg("primary", "Quests", "quests:index", None, 30)
        reg("admin", "Manage quests", "quests:manage", is_admin, 60)
