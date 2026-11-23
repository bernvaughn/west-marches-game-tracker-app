"""Management command to send queued emails and clean up expired payloads."""

from django.core.management.base import BaseCommand

from mail.sending import delete_expired_payloads, send_due_messages


class Command(BaseCommand):
    help = "Send due queued emails and delete expired payloads"

    def handle(self, *args, **options):
        sent, failed = send_due_messages()
        deleted = delete_expired_payloads()

        self.stdout.write(f"Sent: {sent}, Failed: {failed}, Expired payloads deleted: {deleted}")
