from django.apps import AppConfig


class MapConfig(AppConfig):
    name = "map"

    def ready(self):
        from accounts import approvals

        from . import signals  # noqa: F401
        from .approvals import open_map_requests

        approvals.register(open_map_requests)
