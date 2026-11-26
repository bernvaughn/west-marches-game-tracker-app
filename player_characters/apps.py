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
        reg("gm", "All characters", "characters:index", is_gm_or_admin, 60, icon="people")
        reg(
            "gm",
            "Award Loot to Party",
            "characters:bulk_award",
            is_gm_or_admin,
            65,
            icon="cash-stack",
        )
        reg("character", "New character", "characters:create", None, 50, icon="person-plus")
        reg("character", "Character slips", "characters:slips", None, 57, icon="file-earmark-text")
        reg(
            "character",
            "Archived characters",
            "characters:archived",
            lambda r: _membership(r.user, r.club) is not None,
            58,
            icon="archive",
        )
        reg(
            "club",
            "The Fallen",
            "characters:fallen",
            lambda r: _membership(r.user, r.club) is not None,
            59,
            icon="flower1",
            shortcut_order=59,
        )
