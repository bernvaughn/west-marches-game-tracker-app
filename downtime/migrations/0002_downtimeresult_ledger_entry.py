from datetime import timedelta

import django.db.models.deletion
from django.db import migrations, models


def backfill(apps, schema_editor):
    Result = apps.get_model("downtime", "DowntimeResult")
    Entry = apps.get_model("ledger", "LedgerEntry")
    for res in Result.objects.filter(ledger_entry__isnull=True).select_related("action"):
        window = timedelta(seconds=10)
        cands = Entry.objects.filter(
            kind="award",
            character_id=res.character_id,
            note__startswith=f"Downtime: {res.action.name} - ",
            created__gte=res.created - window,
            created__lte=res.created + window,
            downtime_result__isnull=True,
        )
        best = min(cands, key=lambda e: abs(e.created - res.created), default=None)
        if best:
            res.ledger_entry = best
            res.save(update_fields=["ledger_entry"])


class Migration(migrations.Migration):
    dependencies = [
        ("downtime", "0001_initial"),
        ("ledger", "0003_player_shop"),
    ]

    operations = [
        migrations.AddField(
            model_name="downtimeresult",
            name="ledger_entry",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="downtime_result",
                to="ledger.ledgerentry",
            ),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
