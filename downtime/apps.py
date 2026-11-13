from django.apps import AppConfig


class DowntimeConfig(AppConfig):
    name = "downtime"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_gm_or_admin

        reg = navigation.register
        reg("gm", "Downtime points", "downtime:points_award", is_gm_or_admin, 15)
        # Each slice adds its own navigation lines here.
