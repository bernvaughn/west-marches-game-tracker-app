from django.apps import AppConfig


class QuestsConfig(AppConfig):
    name = "quests"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin

        reg = navigation.register
        reg("town", "Quests", "quests:index", None, 30, icon="journal-text", shortcut_order=30)
        reg("admin", "Manage quests", "quests:manage", is_admin, 60)
