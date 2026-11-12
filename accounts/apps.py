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

        approvals.register(open_messages)
        reg = navigation.register
        reg("more", "People", "accounts:index", not_admin, 100)
        reg("more", "Message admins", "accounts:message_new", is_member, 60)
        reg("admin", "Members", "accounts:index", is_admin, 10)
        reg("admin", "Whitelist", "accounts:whitelist", is_admin, 20)
        reg("admin", "Inbox", "accounts:message_inbox", is_admin, 30)
