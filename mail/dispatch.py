"""Dispatch module for notifying the sending subsystem.

M1: mail/sending.py does not exist yet. after_queue is a no-op.
M2: will create mail/sending.py with schedule_send(message).
"""



def after_queue(message) -> None:
    """Called after an email is queued. Notifies the sending module if present."""
    try:
        from mail import sending
    except ImportError as e:
        # When mail.sending doesn't exist, e.name is 'mail'
        if e.name == "mail":
            return
        raise
    sending.schedule_send(message)