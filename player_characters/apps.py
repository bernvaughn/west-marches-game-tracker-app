from django.apps import AppConfig


class PlayerCharactersConfig(AppConfig):
    name = "player_characters"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_gm_or_admin
        from accounts.permissions import _membership

        reg = navigation.register
        reg(
            "character",
            "My character",
            "characters:mine",
            None,
            10,
            icon="person",
            shortcut_order=10,
            shortcut_label="Character",
        )
        reg("character", "Character directory", "characters:directory", None, 15, icon="people")
        reg("character", "All characters", "characters:index", is_gm_or_admin, 60, icon="people")
        reg(
            "downtime",
            "Award loot to party",
            "characters:bulk_award",
            is_gm_or_admin,
            90,
            icon="cash-stack",
        )
        reg("character", "New character", "characters:create", None, 20, icon="person-plus")
        reg("character", "Character slips", "characters:slips", None, 30, icon="file-earmark-text")
        reg(
            "character",
            "Archived characters",
            "characters:archived",
            lambda r: _membership(r.user, r.club) is not None,
            40,
            icon="archive",
        )
        reg(
            "character",
            "The Fallen",
            "characters:fallen",
            lambda r: _membership(r.user, r.club) is not None,
            50,
            icon="flower1",
            shortcut_order=59,
        )
