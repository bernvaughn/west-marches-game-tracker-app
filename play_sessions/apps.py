from django.apps import AppConfig


class PlaySessionsConfig(AppConfig):
    name = "play_sessions"

    def ready(self):
        from . import core

        core.load_hooks()
