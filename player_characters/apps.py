from django.apps import AppConfig


class PlayerCharactersConfig(AppConfig):
    name = "player_characters"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_gm_or_admin

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
        reg("character", "Character directory", "characters:directory", None, 15)
        reg("gm", "All characters", "characters:index", is_gm_or_admin, 60)
        reg(
            "trades", "Trades", "trades:index", None, 20, icon="arrow-left-right", shortcut_order=40
        )
        reg("trades", "Propose trade", "trades:propose", None, 30)
        reg("character", "New character", "characters:create", None, 50)
        reg("character", "Move items", "characters:transfer_start", None, 55)
