"""Mail views package."""

from . import forgot_password
from .contact import contact_email
from .log import clear_flag, email_log
from .test_email import send_test_email
from .webhook import resend_webhook

__all__ = [
    "contact_email",
    "send_test_email",
    "forgot_password",
    "email_log",
    "clear_flag",
    "resend_webhook",
]
