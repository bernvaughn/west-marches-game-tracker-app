from django.apps import AppConfig


class MapConfig(AppConfig):
    name = "map"

    def ready(self):
        from accounts import approvals

        from . import signals  # noqa: F401
        from .approvals import open_map_requests

        approvals.register(open_map_requests)

        from accounts import navigation
        from accounts.apps import is_gm_or_admin

        reg = navigation.register
        reg(
            "map",
            "All maps",
            "map:index",
            None,
            10,
            icon="map",
            shortcut_order=50,
            shortcut_label="Map",
        )
        reg("map", "XP table", "map:xp", None, 120, icon="table")
        reg("map", "Map requests", "map:requests", None, 70, icon="pin-map")
        reg("map", "New map", "map:map_create", is_gm_or_admin, 80, icon="plus-square")
