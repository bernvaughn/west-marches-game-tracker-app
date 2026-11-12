from django.apps import AppConfig


class LedgerConfig(AppConfig):
    name = "ledger"

    def ready(self):
        from accounts import apps as accounts_apps
        from accounts import navigation

        reg = navigation.register
        reg("character", "Ledger", "ledger:index", accounts_apps.not_gm_or_admin, 60)
        reg("gm", "Club ledger", "ledger:index", accounts_apps.is_gm_or_admin, 5)
