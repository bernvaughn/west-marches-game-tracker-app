"""Management command to send a test email directly via Resend."""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send a test email to verify Resend configuration"

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="Email address to send test to")

    def handle(self, *args, **options):
        email = options["email"]

        if not getattr(settings, "RESEND_API_KEY", ""):
            self.stdout.write("Result: bad key (no RESEND_API_KEY configured)")
            return

        try:
            send_mail(
                subject="Test email from Downtime Market",
                message=(
                    "This is a test email from Downtime Market. "
                    "If you received this, Resend is configured correctly."
                ),
                from_email=settings.EMAIL_FROM,
                recipient_list=[email],
                fail_silently=False,
            )
            self.stdout.write("Result: OK")
        except Exception as e:
            error_text = str(e).lower()
            # Also check response body for httpx-style exceptions
            response = getattr(e, "response", None)
            if response is not None:
                error_text += " " + getattr(response, "text", "").lower()
            if (
                "401" in error_text
                or "unauthorized" in error_text
                or "invalid api key" in error_text
            ):
                self.stdout.write("Result: bad key")
            elif "domain" in error_text and (
                "verified" in error_text or "not verified" in error_text
            ):
                self.stdout.write("Result: unverified domain")
            else:
                self.stdout.write(f"Result: error - {type(e).__name__}")
