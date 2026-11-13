from django.apps import AppConfig


class DowntimeConfig(AppConfig):
    name = "downtime"

    def ready(self):
        # Each slice adds its own navigation lines here.
        pass
