# Generated migration for Club.timezone field
from django.db import migrations, models

import accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_sitefeedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="club",
            name="timezone",
            field=models.CharField(
                default=accounts.models.default_timezone,
                help_text="IANA timezone name (e.g., America/New_York)",
                max_length=64,
                validators=[accounts.models.validate_timezone],
            ),
        ),
    ]