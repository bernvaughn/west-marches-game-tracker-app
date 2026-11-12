from django.apps import AppConfig


class MapConfig(AppConfig):
    name = "map"

    def ready(self):
        from accounts import approvals

        from . import signals  # noqa: F401
        from .approvals import open_map_requests

        approvals.register(open_map_requests)

        from accounts import navigation
        from accounts.apps import is_gm_or_admin, not_gm_or_admin

        reg = navigation.register
        reg("more", "Map", "map:index", None, 10)
        reg("more", "XP table", "map:xp", None, 120)
        reg("more", "Map requests", "map:requests", not_gm_or_admin, 70)
        reg("gm", "Map requests", "map:requests", is_gm_or_admin, 10)
        reg("gm", "New map", "map:map_create", is_gm_or_admin, 20)
