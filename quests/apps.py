from django.apps import AppConfig


class QuestsConfig(AppConfig):
    name = "quests"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin

        reg = navigation.register
        reg("quests", "Quests", "quests:index", None, 10, icon="journal-text", shortcut_order=30)
        reg("quests", "Manage quests", "quests:manage", is_admin, 20, icon="journal-check")
