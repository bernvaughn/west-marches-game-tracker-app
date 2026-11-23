"""Hooks for Game Master digest (E7): register the send_digests job."""


def register():
    """Register the digest job. Import happens here to avoid circular imports."""
    # The job is registered in mail.digest via register_job()
    # This module just ensures mail.digest is imported when hooks are loaded.
    import mail.digest  # noqa: F401
