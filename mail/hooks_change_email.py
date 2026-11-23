"""Hooks for email change (E9): register nav entry."""


def register():
    """Register nav entry in the 'account' group."""
    from accounts.navigation import register as register_nav
    from accounts.apps import is_member

    register_nav(
        group="account",
        label="My email address",
        url_name="mail:change_email",
        check=is_member,
        order=10,
    )