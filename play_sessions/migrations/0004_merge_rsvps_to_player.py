# Merge per-character SessionRSVP answers into per-player PlayerRSVP rows.

from django.db import migrations

from play_sessions.models import merge_rsvps_to_player as _merge_rsvps_to_player


def merge_rsvps_to_player(apps, schema_editor):
    """Copy each player's session answers into one PlayerRSVP row.

    Agreeing answers keep that answer; disagreeing answers use the most recent
    by answered_at. answered_by and answered_at are copied from the chosen row.
    Idempotent via get_or_create on (session, member). SessionAttendance is
    never touched. Reversible as a no-op: running backwards keeps the merged
    rows and never deletes SessionRSVP.
    """
    _merge_rsvps_to_player()


class Migration(migrations.Migration):

    dependencies = [
        ("play_sessions", "0003_playerrsvp_attendancehint"),
    ]

    operations = [
        migrations.RunPython(merge_rsvps_to_player, reverse_code=migrations.RunPython.noop),
    ]
