"""Hooks for email preferences (E8/M9): register unsubscribe footer extras and nav entry."""


def register():
    """Register unsubscribe footer extras for optional email kinds and nav entry."""
    from accounts.navigation import register as register_nav
    from mail.builders import register_email_extra
    from mail.preferences import unsubscribe_extra

    # Register unsubscribe footer extras for the canonical email kinds
    # used by M6 (reminders: "reminder"), M8 (digest: "digest"),
    # and M6/M7 (notices: "cancel", "change")
    for kind in ("reminder", "cancel", "change", "digest"):
        register_email_extra(kind, unsubscribe_extra(kind))

    # Register navigation entry: "account" group, "My email", url "mail:preferences"
    # check=membership present (handled by club_member_required on the view)
    register_nav(
        group="account",
        label="My email",
        url_name="mail:preferences",
        check=lambda request: getattr(request, "membership", None) is not None,
        order=10,
    )
