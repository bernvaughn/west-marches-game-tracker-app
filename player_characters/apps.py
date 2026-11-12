from django.apps import AppConfig


class PlayerCharactersConfig(AppConfig):
    name = "player_characters"

    def ready(self):
        from accounts import navigation

        reg = navigation.register
        reg("primary", "Character", "characters:index", None, 10)
        reg("more", "Trades", "trades:index", None, 20)
        reg("more", "Propose trade", "trades:propose", None, 30)
        reg("more", "New character", "characters:create", None, 50)
        reg("more", "Move items", "characters:transfer_start", None, 55)
