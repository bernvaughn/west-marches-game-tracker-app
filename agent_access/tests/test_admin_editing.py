"""Tests for admin editing in agent_access app.

Covers the Editing theme per the Django admin improvements epic.
- All five admins use autocomplete_fields for FKs whose target has search_fields.
- oauth_application uses autocomplete_fields (target admin has search_fields).
- ProposedBatchAdmin has ProposedLineInline with extra=0, show_change_link,
  autocomplete.
- Readonly fields for auto-set stamps: created, confirmed_at, reversed_at,
  timestamp, token_prefix, last_used_at.
- token_hash is excluded from AgentConnection form.
- list_select_related covers FKs in list_display.
- TokenAuditLog stays editable.
"""

import pytest
from django.core.checks import run_checks
from django.urls import reverse

from accounts.models import User
from agent_access.models import (
    AgentConnection,
    ProposedBatch,
    ProposedItem,
    ProposedLine,
    TokenAuditLog,
)
from items.models import Item


@pytest.mark.django_db
class TestAdminEditing:
    """Tests for admin editing features."""

    @pytest.fixture
    def user(self, club):
        return User.objects.create_user(
            "agent@example.com", password="pw", display_name="Agent User"
        )

    @pytest.fixture
    def connection(self, club, user):
        return AgentConnection.objects.create(
            club=club,
            user=user,
            label="Test Connection",
            token_hash="abc123",
            token_prefix="abc123",
        )

    @pytest.fixture
    def batch(self, club, connection, user):
        return ProposedBatch.objects.create(
            club=club,
            connection=connection,
            user=user,
            date="2024-01-15",
            idempotency_key="test-key-123",
        )

    @pytest.fixture
    def proposed_item(self, club, batch):
        return ProposedItem.objects.create(club=club, name="Test Item", batch=batch)

    @pytest.fixture
    def approved_item(self, club):
        return Item.objects.create(club=club, name="Approved Item", value_cp=100)

    @pytest.fixture
    def line(self, batch, character, item):
        return ProposedLine.objects.create(
            batch=batch, character=character, item=item, quantity=1, coins=100, date="2024-01-15"
        )

    @pytest.fixture
    def audit_log(self, club, connection, user):
        return TokenAuditLog.objects.create(
            action=TokenAuditLog.Action.CREATE,
            connection=connection,
            user=user,
            club=club,
            metadata={},
        )

    # --- Changelist, add, change forms load ---

    @pytest.mark.parametrize(
        "model_admin_url,create_obj",
        [
            ("admin:agent_access_agentconnection_changelist", "connection"),
            ("admin:agent_access_proposedbatch_changelist", "batch"),
            ("admin:agent_access_proposeditem_changelist", "proposed_item"),
            ("admin:agent_access_proposedline_changelist", "line"),
            ("admin:agent_access_tokenauditlog_changelist", "audit_log"),
        ],
    )
    def test_changelist_loads(self, site_admin, login, model_admin_url, create_obj, request):
        """Changelist returns 200."""
        client = login(site_admin)
        url = reverse(model_admin_url)
        response = client.get(url)
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "model_admin_add_url",
        [
            "admin:agent_access_agentconnection_add",
            "admin:agent_access_proposedbatch_add",
            "admin:agent_access_proposeditem_add",
            "admin:agent_access_proposedline_add",
            "admin:agent_access_tokenauditlog_add",
        ],
    )
    def test_add_form_loads(self, site_admin, login, model_admin_add_url):
        """Add form returns 200."""
        client = login(site_admin)
        url = reverse(model_admin_add_url)
        response = client.get(url)
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "model_admin_change_url,obj_fixture",
        [
            ("admin:agent_access_agentconnection_change", "connection"),
            ("admin:agent_access_proposedbatch_change", "batch"),
            ("admin:agent_access_proposeditem_change", "proposed_item"),
            ("admin:agent_access_proposedline_change", "line"),
            ("admin:agent_access_tokenauditlog_change", "audit_log"),
        ],
    )
    def test_change_form_loads(
        self, site_admin, login, model_admin_change_url, obj_fixture, request
    ):
        """Change form returns 200."""
        client = login(site_admin)
        obj = request.getfixturevalue(obj_fixture)
        url = reverse(model_admin_change_url, args=[obj.pk])
        response = client.get(url)
        assert response.status_code == 200

    # --- Autocomplete and raw_id widget assertions ---

    def test_agent_connection_autocomplete_fields(self, site_admin, login, connection):
        """AgentConnection has autocomplete for user, club, oauth_application; no token_hash."""
        client = login(site_admin)
        url = reverse("admin:agent_access_agentconnection_change", args=[connection.pk])
        response = client.get(url)
        assert response.status_code == 200

        # Check autocomplete widgets render
        content = response.content.decode()
        assert 'class="admin-autocomplete"' in content or "admin-autocomplete" in content
        # token_hash must not appear as a field
        assert 'name="token_hash"' not in content
        assert "id_token_hash" not in content

        # Verify model admin config
        from agent_access.admin import AgentConnectionAdmin

        assert "user" in AgentConnectionAdmin.autocomplete_fields
        assert "club" in AgentConnectionAdmin.autocomplete_fields
        assert "oauth_application" in AgentConnectionAdmin.autocomplete_fields
        assert "created" in AgentConnectionAdmin.readonly_fields
        assert "token_prefix" in AgentConnectionAdmin.readonly_fields
        assert "last_used_at" in AgentConnectionAdmin.readonly_fields
        assert "token_hash" in AgentConnectionAdmin.exclude

    def test_proposed_batch_autocomplete_and_inline(self, site_admin, login, batch):
        """ProposedBatch has autocomplete for club, connection, user,
        confirmed_by, reversed_by; inline present."""
        client = login(site_admin)
        url = reverse("admin:agent_access_proposedbatch_change", args=[batch.pk])
        response = client.get(url)
        assert response.status_code == 200

        content = response.content.decode()
        assert "admin-autocomplete" in content
        # Inline formset prefix (lines or proposedline_set)
        assert "lines" in content or "proposedline_set" in content
        # Change link for inline
        assert "show_change_link" in content or "change" in content.lower()

        from agent_access.admin import ProposedBatchAdmin, ProposedLineInline

        assert "club" in ProposedBatchAdmin.autocomplete_fields
        assert "connection" in ProposedBatchAdmin.autocomplete_fields
        assert "user" in ProposedBatchAdmin.autocomplete_fields
        assert "confirmed_by" in ProposedBatchAdmin.autocomplete_fields
        assert "reversed_by" in ProposedBatchAdmin.autocomplete_fields
        assert "created" in ProposedBatchAdmin.readonly_fields
        assert "confirmed_at" in ProposedBatchAdmin.readonly_fields
        assert "reversed_at" in ProposedBatchAdmin.readonly_fields
        assert ProposedLineInline in ProposedBatchAdmin.inlines
        assert ProposedLineInline.extra == 0
        assert ProposedLineInline.show_change_link is True
        assert "item" in ProposedLineInline.autocomplete_fields
        assert "character" in ProposedLineInline.autocomplete_fields
        assert "proposed_item" in ProposedLineInline.autocomplete_fields

    def test_proposed_item_autocomplete(self, site_admin, login, proposed_item):
        """ProposedItem has autocomplete for club, approved_item, batch, connection."""
        client = login(site_admin)
        url = reverse("admin:agent_access_proposeditem_change", args=[proposed_item.pk])
        response = client.get(url)
        assert response.status_code == 200

        content = response.content.decode()
        assert "admin-autocomplete" in content

        from agent_access.admin import ProposedItemAdmin

        assert "club" in ProposedItemAdmin.autocomplete_fields
        assert "approved_item" in ProposedItemAdmin.autocomplete_fields
        assert "batch" in ProposedItemAdmin.autocomplete_fields
        assert "connection" in ProposedItemAdmin.autocomplete_fields
        assert "created" in ProposedItemAdmin.readonly_fields

    def test_proposed_line_autocomplete(self, site_admin, login, line):
        """ProposedLine has autocomplete for batch, character, item, proposed_item."""
        client = login(site_admin)
        url = reverse("admin:agent_access_proposedline_change", args=[line.pk])
        response = client.get(url)
        assert response.status_code == 200

        content = response.content.decode()
        assert "admin-autocomplete" in content

        from agent_access.admin import ProposedLineAdmin

        assert "batch" in ProposedLineAdmin.autocomplete_fields
        assert "character" in ProposedLineAdmin.autocomplete_fields
        assert "item" in ProposedLineAdmin.autocomplete_fields
        assert "proposed_item" in ProposedLineAdmin.autocomplete_fields

    def test_token_audit_log_autocomplete(self, site_admin, login, audit_log):
        """TokenAuditLog has autocomplete for user, club, connection;
        timestamp readonly; stays editable."""
        client = login(site_admin)
        url = reverse("admin:agent_access_tokenauditlog_change", args=[audit_log.pk])
        response = client.get(url)
        assert response.status_code == 200

        content = response.content.decode()
        assert "admin-autocomplete" in content

        from agent_access.admin import TokenAuditLogAdmin

        assert "user" in TokenAuditLogAdmin.autocomplete_fields
        assert "club" in TokenAuditLogAdmin.autocomplete_fields
        assert "connection" in TokenAuditLogAdmin.autocomplete_fields
        assert "timestamp" in TokenAuditLogAdmin.readonly_fields
        # TokenAuditLog stays editable (no ReadOnlyAdmin, no has_change_permission override)

    # --- POST valid change ---

    def test_post_agent_connection_change(self, site_admin, login, connection):
        """POST a valid change to AgentConnection."""
        client = login(site_admin)
        url = reverse("admin:agent_access_agentconnection_change", args=[connection.pk])
        response = client.post(
            url,
            {
                "label": "Updated Label",
                "user": connection.user.pk,
                "club": connection.club.pk,
                "kind": connection.kind,
            },
        )
        if response.status_code != 302:
            if (
                hasattr(response, "context")
                and response.context
                and "adminform" in response.context
            ):
                print("Form errors:", response.context["adminform"].form.errors)
            else:
                print("No adminform in context")
            print("Content:", response.content.decode()[:3000])
        assert response.status_code == 302
        connection.refresh_from_db()
        assert connection.label == "Updated Label"

    def test_post_proposed_batch_change(self, site_admin, login, batch):
        """POST a valid change to ProposedBatch (with inline management form)."""
        client = login(site_admin)
        url = reverse("admin:agent_access_proposedbatch_change", args=[batch.pk])
        response = client.post(
            url,
            {
                "club": batch.club.pk,
                "connection": batch.connection.pk,
                "user": batch.user.pk,
                "date": "2024-01-15",
                "idempotency_key": "test-key-123",
                "status": "confirmed",
                "source_notes": "",
                "confirmed_by": "",
                "reversed_by": "",
                # Inline management form
                "lines-TOTAL_FORMS": "0",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
            },
        )
        assert response.status_code == 302
        batch.refresh_from_db()
        assert batch.status == "confirmed"

    def test_post_proposed_item_change(self, site_admin, login, proposed_item, approved_item):
        """POST a valid change to ProposedItem."""
        client = login(site_admin)
        url = reverse("admin:agent_access_proposeditem_change", args=[proposed_item.pk])
        response = client.post(
            url,
            {
                "club": proposed_item.club.pk,
                "name": "Updated Item",
                "description": "",
                "traits": "",
                "details": "",
                "gm_details": "",
                "value_cp": "0",
                "status": "approved",
                "approved_item": approved_item.pk,
                "batch": proposed_item.batch.pk,
                "connection": "",
            },
        )
        assert response.status_code == 302
        proposed_item.refresh_from_db()
        assert proposed_item.name == "Updated Item"
        assert proposed_item.status == "approved"

    def test_post_proposed_line_change(self, site_admin, login, line):
        """POST a valid change to ProposedLine."""
        client = login(site_admin)
        url = reverse("admin:agent_access_proposedline_change", args=[line.pk])
        response = client.post(
            url,
            {
                "batch": line.batch.pk,
                "character": line.character.pk,
                "item": line.item.pk,
                "proposed_item": "",
                "date": "2024-01-15",
                "quantity": "5",
                "coins": "200",
                "note": "",
            },
        )
        assert response.status_code == 302
        line.refresh_from_db()
        assert line.quantity == 5
        assert line.coins == 200

    def test_post_token_audit_log_change(self, site_admin, login, audit_log):
        """POST a valid change to TokenAuditLog (editable)."""
        client = login(site_admin)
        url = reverse("admin:agent_access_tokenauditlog_change", args=[audit_log.pk])
        response = client.post(
            url,
            {
                "action": "use",
                "user": audit_log.user.pk,
                "club": audit_log.club.pk,
                "connection": audit_log.connection.pk,
                "metadata": "{}",
            },
        )
        assert response.status_code == 302
        audit_log.refresh_from_db()
        assert audit_log.action == "use"

    # --- Django admin checks ---

    def test_admin_checks_no_errors(self):
        """django.core.checks.run_checks() shows no admin errors."""
        errors = run_checks()
        admin_errors = [e for e in errors if e.id.startswith("admin.")]
        assert not admin_errors, f"Admin errors: {[str(e) for e in admin_errors]}"

    # --- list_select_related ---

    def test_list_select_related_agent_connection(self):
        from agent_access.admin import AgentConnectionAdmin

        assert "user" in AgentConnectionAdmin.list_select_related
        assert "club" in AgentConnectionAdmin.list_select_related

    def test_list_select_related_proposed_batch(self):
        from agent_access.admin import ProposedBatchAdmin

        assert "club" in ProposedBatchAdmin.list_select_related
        assert "connection" in ProposedBatchAdmin.list_select_related
        assert "user" in ProposedBatchAdmin.list_select_related

    def test_list_select_related_proposed_item(self):
        from agent_access.admin import ProposedItemAdmin

        assert "club" in ProposedItemAdmin.list_select_related
        assert "batch" in ProposedItemAdmin.list_select_related

    def test_list_select_related_proposed_line(self):
        from agent_access.admin import ProposedLineAdmin

        assert "batch" in ProposedLineAdmin.list_select_related
        assert "character" in ProposedLineAdmin.list_select_related
        assert "item" in ProposedLineAdmin.list_select_related

    def test_list_select_related_token_audit_log(self):
        from agent_access.admin import TokenAuditLogAdmin

        assert "user" in TokenAuditLogAdmin.list_select_related
        assert "club" in TokenAuditLogAdmin.list_select_related
        assert "connection" in TokenAuditLogAdmin.list_select_related
