"""Delete email messages older than 90 days."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mail.models import EmailMessage


class Command(BaseCommand):
    help = "Delete email messages older than 90 days"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=90)
        deleted_count, _ = EmailMessage.objects.filter(created__lt=cutoff).delete()
        self.stdout.write(f"Deleted {deleted_count} email messages older than 90 days")
