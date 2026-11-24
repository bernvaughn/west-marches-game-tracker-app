"""Tests for admin list pages in agent_access app."""

import pytest
from django.urls import reverse

from accounts.models import User
from agent_access.models import AgentConnection, ProposedBatch, ProposedItem, ProposedLine


@pytest.mark.django_db
def test_agent_connection_admin_changelist_and_change(site_admin, club, login):
    """AgentConnection changelist loads and change form works."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:agent_access_agentconnection_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    user = User.objects.create_user("agent@example.com", password="pw", display_name="Agent User")
    conn = AgentConnection.objects.create(club=club, user=user, label="Test Connection")
    url = reverse("admin:agent_access_agentconnection_change", args=[conn.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_proposed_batch_admin_changelist_and_change(site_admin, club, login):
    """ProposedBatch changelist loads and change form works."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:agent_access_proposedbatch_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    user = User.objects.create_user("agent@example.com", password="pw", display_name="Agent User")
    conn = AgentConnection.objects.create(club=club, user=user, label="Test Connection")
    batch = ProposedBatch.objects.create(
        club=club,
        connection=conn,
        user=user,
        date="2024-01-15",
        idempotency_key="test-key-123",
    )
    url = reverse("admin:agent_access_proposedbatch_change", args=[batch.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_proposed_item_admin_changelist_and_change(site_admin, club, login):
    """ProposedItem changelist loads and change form works."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:agent_access_proposeditem_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    user = User.objects.create_user("agent@example.com", password="pw", display_name="Agent User")
    conn = AgentConnection.objects.create(club=club, user=user, label="Test Connection")
    batch = ProposedBatch.objects.create(
        club=club,
        connection=conn,
        user=user,
        date="2024-01-15",
        idempotency_key="test-key-123",
    )
    item = ProposedItem.objects.create(club=club, name="Test Item", batch=batch)
    url = reverse("admin:agent_access_proposeditem_change", args=[item.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_proposed_line_admin_changelist_and_change(site_admin, club, character, item, login):
    """ProposedLine changelist loads and change form works."""
    client = login(site_admin)

    # Changelist
    url = reverse("admin:agent_access_proposedline_changelist")
    response = client.get(url)
    assert response.status_code == 200

    # Create instance and test change form
    user = User.objects.create_user("agent@example.com", password="pw", display_name="Agent User")
    conn = AgentConnection.objects.create(club=club, user=user, label="Test Connection")
    batch = ProposedBatch.objects.create(
        club=club,
        connection=conn,
        user=user,
        date="2024-01-15",
        idempotency_key="test-key-123",
    )
    line = ProposedLine.objects.create(
        batch=batch, character=character, item=item, quantity=1, coins=100, date="2024-01-15"
    )
    url = reverse("admin:agent_access_proposedline_change", args=[line.pk])
    response = client.get(url)
    assert response.status_code == 200
