from django.apps import AppConfig


def is_admin(r):
    return bool(r.user.is_superuser or (r.membership and r.membership.is_club_admin))


def is_gm(r):
    return bool(r.user.is_superuser or (r.membership and r.membership.is_game_master))


def is_gm_or_admin(r):
    return bool(
        r.user.is_superuser
        or (r.membership and (r.membership.is_game_master or r.membership.is_club_admin))
    )


def is_member(r):
    return r.membership is not None


def not_admin(r):
    return not is_admin(r)


def not_gm_or_admin(r):
    return not is_gm_or_admin(r)


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        from . import approvals, navigation
        from .approval_providers import open_messages
        from .dashboard_providers import (
            ConsumablesDashboardProvider,
            DowntimeDashboardProvider,
            HeaderDashboardProvider,
            MapDashboardProvider,
            MessagesDashboardProvider,
            MyMessagesDashboardProvider,
            PlayerShopDashboardProvider,
            QuestsDashboardProvider,
            QuickActionsProvider,
            register_provider,
        )

        approvals.register(open_messages)
        register_provider(QuickActionsProvider())
        reg = navigation.register
        reg(
            "character",
            "Dashboard",
            "accounts:player_dashboard",
            is_member,
            5,
            icon="speedometer2",
            shortcut_order=0,
            shortcut_label="Dashboard",
            also_current=("club_home",),
        )
        reg("club", "People", "accounts:index", not_admin, 100)
        reg("club", "Message the admins", "accounts:message_new", is_member, 60)
        reg("club", "Request stock", "accounts:stock_request_new", is_member, 65)
        reg("admin", "Members", "accounts:index", is_admin, 10)
        reg("admin", "Whitelist", "accounts:whitelist", is_admin, 20)
        reg("admin", "Inbox", "accounts:message_inbox", is_admin, 30)

        # Register built-in dashboard providers
        register_provider(HeaderDashboardProvider())
        register_provider(QuestsDashboardProvider())
        register_provider(DowntimeDashboardProvider())
        register_provider(MapDashboardProvider())
        register_provider(MessagesDashboardProvider())
        register_provider(MyMessagesDashboardProvider())
        register_provider(PlayerShopDashboardProvider())
        register_provider(ConsumablesDashboardProvider())
