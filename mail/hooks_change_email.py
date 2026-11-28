"""Hooks for email change (E9): register nav entry."""


def register():
    """Register nav entry in the 'mail' group."""
    from accounts.apps import is_member
    from accounts.navigation import register as register_nav

    register_nav(
        group="mail",
        label="My email address",
        url_name="mail:change_email",
        icon="at",
        check=is_member,
        order=10,
    )
