from django.apps import AppConfig


class CharacterOptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "character_options"
    verbose_name = "Character Options"

    def ready(self):
        from accounts.apps import is_admin
        from accounts.navigation import register

        register(
            "items",
            "Character options",
            "character_options:index",
            is_admin,
            56,
            icon="sliders",
        )
