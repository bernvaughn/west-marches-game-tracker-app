from django.apps import AppConfig


class PlayerCharactersConfig(AppConfig):
    name = "player_characters"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_gm_or_admin

        reg = navigation.register
        reg("primary", "Character", "characters:mine", None, 10)
        reg("more", "Character directory", "characters:directory", None, 15)
        reg("gm", "All characters", "characters:index", is_gm_or_admin, 60)
        reg("more", "Trades", "trades:index", None, 20)
        reg("more", "Propose trade", "trades:propose", None, 30)
        reg("more", "New character", "characters:create", None, 50)
        reg("more", "Move items", "characters:transfer_start", None, 55)
