"""Test downtime admin changelists, change forms, read-only models and bulk actions."""

import pytest
from django.urls import reverse

from downtime.models import (
    DowntimeAction,
    DowntimeEntryItem,
    DowntimePointEntry,
    DowntimePointRequest,
    DowntimeResult,
)


@pytest.mark.django_db
def test_downtimepointentry_admin_changelist_and_change(site_admin, login, character):
    """DowntimePointEntry changelist and change form load."""
    entry = DowntimePointEntry.objects.create(
        character=character,
        delta=5,
        kind=DowntimePointEntry.Kind.AWARD,
    )
    client = login(site_admin)

    url = reverse("admin:downtime_downtimepointentry_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert character.name.encode() in response.content

    url = reverse("admin:downtime_downtimepointentry_change", args=[entry.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert character.name.encode() in response.content


@pytest.mark.django_db
def test_downtimepointentry_admin_no_add(site_admin, login):
    """DowntimePointEntry admin has no add permission."""
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointentry_add")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_downtimepointentry_admin_change_readonly(site_admin, login, character):
    """DowntimePointEntry admin change view is read-only (no save buttons)."""
    entry = DowntimePointEntry.objects.create(
        character=character, delta=5, kind=DowntimePointEntry.Kind.AWARD
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointentry_change", args=[entry.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert 'name="_addanother"' not in content


@pytest.mark.django_db
def test_downtimepointentry_admin_no_delete(site_admin, login, character):
    """DowntimePointEntry admin has no delete permission."""
    entry = DowntimePointEntry.objects.create(
        character=character, delta=5, kind=DowntimePointEntry.Kind.AWARD
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointentry_delete", args=[entry.pk])
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_downtimeaction_admin_changelist_and_change(site_admin, login, club):
    """DowntimeAction changelist and change form load."""
    action = DowntimeAction.objects.create(club=club, name="Work at a bakery", cost=2)
    client = login(site_admin)

    url = reverse("admin:downtime_downtimeaction_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert b"Work at a bakery" in response.content

    url = reverse("admin:downtime_downtimeaction_change", args=[action.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert b"Work at a bakery" in response.content


@pytest.mark.django_db
def test_downtimeentry_admin_changelist_and_change(site_admin, login, entry):
    """DowntimeEntry changelist and change form load."""
    client = login(site_admin)

    url = reverse("admin:downtime_downtimeentry_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert entry.label.encode() in response.content

    url = reverse("admin:downtime_downtimeentry_change", args=[entry.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert entry.label.encode() in response.content


@pytest.mark.django_db
def test_downtimeentryitem_admin_changelist_and_change(site_admin, login, entry, item):
    """DowntimeEntryItem changelist and change form load."""
    entry_item = DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=2)
    client = login(site_admin)

    url = reverse("admin:downtime_downtimeentryitem_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert item.name.encode() in response.content
    assert b"2" in response.content

    url = reverse("admin:downtime_downtimeentryitem_change", args=[entry_item.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert item.name.encode() in response.content


@pytest.mark.django_db
def test_downtimeresult_admin_changelist_and_change(site_admin, login, character, action, entry):
    """DowntimeResult changelist and change form load."""
    result = DowntimeResult.objects.create(character=character, action=action, entry=entry)
    client = login(site_admin)

    url = reverse("admin:downtime_downtimeresult_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert character.name.encode() in response.content

    url = reverse("admin:downtime_downtimeresult_change", args=[result.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert character.name.encode() in response.content


@pytest.mark.django_db
def test_downtimeresult_admin_no_add(site_admin, login):
    """DowntimeResult admin has no add permission."""
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeresult_add")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_downtimeresult_admin_change_readonly(site_admin, login, character, action, entry):
    """DowntimeResult admin change view is read-only (no save buttons)."""
    result = DowntimeResult.objects.create(character=character, action=action, entry=entry)
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeresult_change", args=[result.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert 'name="_addanother"' not in content


@pytest.mark.django_db
def test_downtimeresult_admin_no_delete(site_admin, login, character, action, entry):
    """DowntimeResult admin has no delete permission."""
    result = DowntimeResult.objects.create(character=character, action=action, entry=entry)
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeresult_delete", args=[result.pk])
    response = client.post(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_downtimepointrequest_admin_changelist_and_change(site_admin, login, point_request):
    """DowntimePointRequest changelist and change form load."""
    client = login(site_admin)

    url = reverse("admin:downtime_downtimepointrequest_changelist")
    response = client.get(url)
    assert response.status_code == 200
    assert str(point_request.points).encode() in response.content

    url = reverse("admin:downtime_downtimepointrequest_change", args=[point_request.pk])
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_downtimepointrequest_admin_approve_requests(site_admin, login, club, player):
    """Approve selected pending requests."""
    membership = player.memberships.get(club=club)
    req = DowntimePointRequest.objects.create(
        club=club,
        requested_by=membership,
        points=3,
        status=DowntimePointRequest.Status.PENDING,
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointrequest_changelist")
    response = client.post(
        url,
        {"action": "approve_requests", "_selected_action": [req.pk]},
    )
    assert response.status_code == 302
    req.refresh_from_db()
    assert req.status == DowntimePointRequest.Status.APPROVED
    assert req.decided_at is not None


@pytest.mark.django_db
def test_downtimepointrequest_admin_decline_requests(site_admin, login, club, player):
    """Decline selected pending requests."""
    membership = player.memberships.get(club=club)
    req = DowntimePointRequest.objects.create(
        club=club,
        requested_by=membership,
        points=3,
        status=DowntimePointRequest.Status.PENDING,
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointrequest_changelist")
    response = client.post(
        url,
        {"action": "decline_requests", "_selected_action": [req.pk]},
    )
    assert response.status_code == 302
    req.refresh_from_db()
    assert req.status == DowntimePointRequest.Status.DECLINED
    assert req.decided_at is not None
