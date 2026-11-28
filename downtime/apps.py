from django.apps import AppConfig


class DowntimeConfig(AppConfig):
    name = "downtime"

    def ready(self):
        from accounts import approvals, navigation
        from accounts.apps import is_admin, is_gm_or_admin

        from .approvals import pending_point_requests

        approvals.register(pending_point_requests)

        reg = navigation.register
        reg("downtime", "Downtime points", "downtime:points_award", is_gm_or_admin, 85, icon="coin")
        reg(
            "downtime",
            "Downtime",
            "downtime:play",
            None,
            35,
            icon="hourglass-split",
            shortcut_order=35,
        )
        reg("downtime", "Agenda", "downtime:agenda", is_admin, 90, icon="calendar-event")
        reg("downtime", "Downtime actions", "downtime:actions", is_admin, 95, icon="list-task")
        reg(
            "downtime",
            "Downtime requests",
            "downtime:requests",
            None,
            80,
            icon="hourglass-split",
        )
