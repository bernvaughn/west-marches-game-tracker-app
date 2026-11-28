from django.apps import AppConfig


class LedgerConfig(AppConfig):
    name = "ledger"

    def ready(self):
        from accounts import navigation

        reg = navigation.register
        reg(
            "downtime",
            "Ledger",
            "ledger:index",
            None,
            40,
            icon="journal-text",
        )
