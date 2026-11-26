# Merge per-character SessionRSVP answers into per-player PlayerRSVP rows.

from django.db import migrations


def merge_rsvps_to_player(apps, schema_editor):
    """Copy each player's session answers into one PlayerRSVP row.

    Agreeing answers keep that answer; disagreeing answers use the most recent
    by answered_at. answered_by and answered_at are copied from the chosen row.
    Idempotent via get_or_create on (session, member). SessionAttendance is
    never touched. Reversible as a no-op: running backwards keeps the merged
    rows and never deletes SessionRSVP.
    """
    SessionRSVP = apps.get_model("play_sessions", "SessionRSVP")
    PlayerRSVP = apps.get_model("play_sessions", "PlayerRSVP")

    from django.db import transaction

    merged = 0
    mixed = 0

    rsvps = SessionRSVP.objects.select_related("character__owner").order_by(
        "session_id", "character__owner_id", "-answered_at", "-id"
    )

    current_key = None
    group = []

    def flush():
        nonlocal merged, mixed
        if current_key is None:
            return
        session_id, member_id = current_key
        answers = {row.answer for row in group}
        chosen = group[0]  # most recent by answered_at, then id
        if len(answers) != 1:
            mixed += 1
        _, created = PlayerRSVP.objects.get_or_create(
            session_id=session_id,
            member_id=member_id,
            defaults={
                "answer": chosen.answer,
                "answered_by_id": chosen.answered_by_id,
                "answered_at": chosen.answered_at,
            },
        )
        if created:
            merged += 1

    with transaction.atomic():
        for row in rsvps:
            member_id = row.character.owner_id
            if member_id is None:
                continue
            key = (row.session_id, member_id)
            if key != current_key:
                flush()
                current_key = key
                group = []
            group.append(row)
        flush()

    return merged, mixed


class Migration(migrations.Migration):

    dependencies = [
        ("play_sessions", "0003_playerrsvp_attendancehint"),
    ]

    operations = [
        migrations.RunPython(merge_rsvps_to_player, reverse_code=migrations.RunPython.noop),
    ]