"""Management command to run all mail jobs including sending queued emails."""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from mail.jobs import registered_jobs
from mail.models import JobRun


class Command(BaseCommand):
    help = "Run queued email sending and all registered mail jobs"

    def handle(self, *args, **options):
        # First, send queued emails
        call_command("send_queued_email")

        # Then run all registered jobs
        for name, fn in registered_jobs():
            run_at = timezone.now()
            ok = True
            note = ""
            try:
                fn()
            except Exception as e:
                ok = False
                note = f"{type(e).__name__}: {e}"
                self.stderr.write(f"Job {name} failed: {note}")

            # Record the job run
            JobRun.objects.update_or_create(
                name=name,
                defaults={
                    "last_run_at": run_at,
                    "ok": ok,
                    "note": note,
                },
            )

        self.stdout.write("Mail jobs completed")
