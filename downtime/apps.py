from django.apps import AppConfig


class DowntimeConfig(AppConfig):
    name = "downtime"

    def ready(self):
        from accounts import approvals, navigation
        from accounts.apps import is_admin, is_gm_or_admin, not_gm_or_admin

        from .approvals import pending_point_requests

        approvals.register(pending_point_requests)

        reg = navigation.register
        # Each slice adds its own navigation lines here.
        reg("gm", "Downtime points", "downtime:points_award", is_gm_or_admin, 15)
        reg(
            "town", "Downtime", "downtime:play", None, 35, icon="hourglass-split", shortcut_order=35
        )
        reg("admin", "Downtime actions", "downtime:actions", is_admin, 70)
        reg("character", "Request downtime points", "downtime:requests", not_gm_or_admin, 80)
        reg("gm", "Downtime point requests", "downtime:requests", is_gm_or_admin, 80)
