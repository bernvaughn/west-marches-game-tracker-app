from django.apps import AppConfig


class MapConfig(AppConfig):
    name = "map"

    def ready(self):
        from . import signals  # noqa: F401
