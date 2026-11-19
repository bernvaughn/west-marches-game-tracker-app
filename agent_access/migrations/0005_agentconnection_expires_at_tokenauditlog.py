# Generated migration for token expiration and audit logging

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
        ("agent_access", "0004_proposeditem_gm_details"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add expires_at field to AgentConnection
        migrations.AddField(
            model_name="agentconnection",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Create TokenAuditLog model
        migrations.CreateModel(
            name="TokenAuditLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("action", models.CharField(choices=[("create", "Create"), ("use", "Use"), ("revoke", "Revoke"), ("expire", "Expire")], max_length=10)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("connection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_logs", to="agent_access.agentconnection")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="token_audit_logs", to="accounts.user")),
                ("club", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="token_audit_logs", to="accounts.club")),
            ],
            options={
                "ordering": ["-timestamp"],
            },
        ),
        # Add indexes for TokenAuditLog
        migrations.AddIndex(
            model_name="tokenauditlog",
            index=models.Index(fields=["action"], name="tokenauditlog_action_idx"),
        ),
        migrations.AddIndex(
            model_name="tokenauditlog",
            index=models.Index(fields=["user"], name="tokenauditlog_user_idx"),
        ),
        migrations.AddIndex(
            model_name="tokenauditlog",
            index=models.Index(fields=["club"], name="tokenauditlog_club_idx"),
        ),
        migrations.AddIndex(
            model_name="tokenauditlog",
            index=models.Index(fields=["timestamp"], name="tokenauditlog_timestamp_idx"),
        ),
    ]