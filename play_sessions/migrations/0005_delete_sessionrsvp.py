# Drop the SessionRSVP table after all code has been switched to PlayerRSVP.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("play_sessions", "0004_merge_rsvps_to_player"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SessionRSVP",
        ),
    ]