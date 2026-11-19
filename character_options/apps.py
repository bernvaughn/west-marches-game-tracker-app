from django.apps import AppConfig


class CharacterOptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "character_options"
    verbose_name = "Character Options"

    def ready(self):
        # Navigation registration stub for the admin group.
        # The admin UI child will uncomment and point to a real URL once views exist.
        # from accounts.navigation import register
        # from accounts.permissions import is_club_admin as is_admin
        # register(
        #     "admin",
        #     "Character options",
        #     "character_options:index",
        #     is_admin,
        #     50,
        # )
        pass
