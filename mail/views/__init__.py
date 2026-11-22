"""Mail views package."""

from .contact import contact_email
from .test_email import send_test_email

__all__ = ["contact_email", "send_test_email"]
