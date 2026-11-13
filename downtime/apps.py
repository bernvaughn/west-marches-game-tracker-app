from django.apps import AppConfig


class DowntimeConfig(AppConfig):
    name = "downtime"

    def ready(self):
        from accounts import navigation
        from accounts.apps import is_admin, is_gm_or_admin

        reg = navigation.register
        # Each slice adds its own navigation lines here.
        reg("gm", "Downtime points", "downtime:points_award", is_gm_or_admin, 15)
        reg(
            "town", "Downtime", "downtime:play", None, 35, icon="hourglass-split", shortcut_order=35
        )
        reg("admin", "Downtime actions", "downtime:actions", is_admin, 70)
