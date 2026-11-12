from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        from . import approvals
        from .approval_providers import open_messages

        approvals.register(open_messages)
