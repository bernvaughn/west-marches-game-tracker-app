from django.apps import AppConfig


class LedgerConfig(AppConfig):
    name = "ledger"

    def ready(self):
        from accounts import navigation

        reg = navigation.register
        reg("more", "Ledger", "ledger:index", None, 40)
