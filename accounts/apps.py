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


def has_donate_url(r):
    from .models import SiteSettings
    return bool(SiteSettings.load().donate_url)


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
            NoticesDashboardProvider,
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
        reg("club", "People", "accounts:index", not_admin, 100, icon="people")
        reg("club", "Message the admins", "accounts:message_new", is_member, 60, icon="chat-left-text")
        reg("club", "Request stock", "accounts:stock_request_new", is_member, 65, icon="box-arrow-up")
        reg("admin", "Members", "accounts:index", is_admin, 10, icon="people")
        reg("admin", "Whitelist", "accounts:whitelist", is_admin, 20, icon="person-check")
        reg("admin", "Inbox", "accounts:message_inbox", is_admin, 30, icon="inbox")
        reg("admin", "Club settings", "accounts:club_settings", is_admin, 40, icon="gear")

        # Account links (visible to all authenticated users, not club-specific)
        reg("account", "Your clubs", "home", lambda r: True, 10, icon="houses", club_required=False)
        reg("account", "Change password", "password_change", lambda r: True, 20, icon="key", club_required=False)
        reg("account", "Donate", "donate", has_donate_url, 30, icon="heart", club_required=False)

        # Register built-in dashboard providers
        register_provider(HeaderDashboardProvider())
        register_provider(QuestsDashboardProvider())
        register_provider(NoticesDashboardProvider())
        register_provider(DowntimeDashboardProvider())
        register_provider(MapDashboardProvider())
        register_provider(MessagesDashboardProvider())
        register_provider(MyMessagesDashboardProvider())
        register_provider(PlayerShopDashboardProvider())
        register_provider(ConsumablesDashboardProvider())