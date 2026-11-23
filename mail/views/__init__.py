"""Mail views package."""

from . import forgot_password
from .contact import contact_email
from .test_email import send_test_email

__all__ = ["contact_email", "send_test_email", "forgot_password"]
