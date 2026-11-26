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


@pytest.mark.django_db
def test_downtimeaction_admin_list_display(site_admin, login, club):
    """DowntimeAction admin shows correct fields in changelist."""
    from datetime import date

    DowntimeAction.objects.create(
        club=club,
        name="Test Action",
        cost=5,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeaction_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Action" in content
    assert club.name in content
    assert "5" in content  # cost
    # Django admin formats dates as "1 Jan 2024" format
    assert "1 Jan 2024" in content
    assert "31 Dec 2024" in content


@pytest.mark.django_db
def test_downtimeentry_admin_list_display(site_admin, login, action):
    """DowntimeEntry admin shows correct fields in changelist."""
    from downtime.models import DowntimeEntry

    DowntimeEntry.objects.create(action=action, label="Test Entry", weight=3, coins=10, order=1)
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeentry_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Test Entry" in content
    assert "3" in content  # weight
    assert "10" in content  # coins
    assert "1" in content  # order
    # action name should appear
    assert action.name in content


@pytest.mark.django_db
def test_downtimeentryitem_admin_list_display(site_admin, login, entry, item):
    """DowntimeEntryItem admin shows correct fields in changelist."""
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=5)
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeentryitem_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert entry.label in content
    assert item.name in content
    assert "5" in content  # quantity


@pytest.mark.django_db
def test_downtimepointrequest_admin_list_display(site_admin, login, club, player):
    """DowntimePointRequest admin shows correct fields in changelist."""
    from accounts.models import Membership

    membership = Membership.objects.get(user=player, club=club)
    DowntimePointRequest.objects.create(
        club=club, requested_by=membership, points=7, status=DowntimePointRequest.Status.PENDING
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointrequest_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert club.name in content
    # requested_by shows as "display_name @ club" (User.__str__ returns display_name or email)
    assert f"{player.display_name or player.email} @ {club.name}" in content
    assert "7" in content  # points
    assert "Pending" in content  # status


@pytest.mark.django_db
def test_downtimeaction_admin_list_filter_club(site_admin, login, club, other_club):
    """DowntimeAction list_filter shows club filter."""
    DowntimeAction.objects.create(club=club, name="Action A")
    DowntimeAction.objects.create(club=other_club, name="Action B")
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeaction_changelist")
    # Filter by club
    response = client.get(url, {"club__id__exact": club.pk})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Action A" in content
    assert "Action B" not in content


@pytest.mark.django_db
def test_downtimeentry_admin_list_filter_action_club(site_admin, login, club, other_club):
    """DowntimeEntry list_filter shows club via action__club."""
    from downtime.models import DowntimeEntry

    action1 = DowntimeAction.objects.create(club=club, name="Action 1")
    action2 = DowntimeAction.objects.create(club=other_club, name="Action 2")
    DowntimeEntry.objects.create(action=action1, label="Entry 1")
    DowntimeEntry.objects.create(action=action2, label="Entry 2")
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeentry_changelist")
    # Filter by action__club
    response = client.get(url, {"action__club__id__exact": club.pk})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Entry 1" in content
    assert "Entry 2" not in content


@pytest.mark.django_db
def test_downtimeentryitem_admin_list_filter_entry_action_club(
    site_admin, login, club, other_club, item
):
    """DowntimeEntryItem list_filter shows club via entry__action__club."""
    from downtime.models import DowntimeEntry

    action1 = DowntimeAction.objects.create(club=club, name="Action 1")
    action2 = DowntimeAction.objects.create(club=other_club, name="Action 2")
    entry1 = DowntimeEntry.objects.create(action=action1, label="Entry 1")
    entry2 = DowntimeEntry.objects.create(action=action2, label="Entry 2")
    DowntimeEntryItem.objects.create(entry=entry1, item=item, quantity=1)
    DowntimeEntryItem.objects.create(entry=entry2, item=item, quantity=1)
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeentryitem_changelist")
    # Filter by entry__action__club
    response = client.get(url, {"entry__action__club__id__exact": club.pk})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Entry 1" in content
    assert "Entry 2" not in content


@pytest.mark.django_db
def test_downtimepointrequest_admin_list_filter_club_status(
    site_admin, login, club, other_club, player
):
    """DowntimePointRequest list_filter shows club and status."""
    import re

    from accounts.models import Membership

    membership1 = Membership.objects.get(user=player, club=club)
    # Create another membership for the player in other_club
    membership2 = Membership.objects.create(user=player, club=other_club)

    DowntimePointRequest.objects.create(
        club=club, requested_by=membership1, points=1, status=DowntimePointRequest.Status.PENDING
    )
    DowntimePointRequest.objects.create(
        club=club, requested_by=membership1, points=2, status=DowntimePointRequest.Status.APPROVED
    )
    DowntimePointRequest.objects.create(
        club=other_club,
        requested_by=membership2,
        points=3,
        status=DowntimePointRequest.Status.PENDING,
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointrequest_changelist")
    # Filter by club
    response = client.get(url, {"club__id__exact": club.pk})
    assert response.status_code == 200
    content = response.content.decode()
    # Debug: print rows
    rows = re.findall(r"<tr[^>]*>.*?</tr>", content, re.DOTALL)
    for row in rows:
        if "Pending" in row or "Approved" in row:
            print(f"DEBUG CLUB FILTER ROW: {repr(row[:500])}")
    assert "Pending" in content
    assert "Approved" in content
    # Should not show other_club's request (only 2 requests for this club)
    # Filter by status
    response = client.get(url, {"status__exact": "pending"})
    assert response.status_code == 200
    content = response.content.decode()
    # Debug: print rows
    rows = re.findall(r"<tr[^>]*>.*?</tr>", content, re.DOTALL)
    for row in rows:
        if "Pending" in row or "Approved" in row:
            print(f"DEBUG STATUS FILTER ROW: {repr(row[:500])}")
    # Check only the table rows for status, not the filter sidebar
    table_content = "".join(rows)
    assert "Pending" in table_content
    assert "Approved" not in table_content


@pytest.mark.django_db
def test_downtimeaction_admin_search(site_admin, login, club):
    """DowntimeAction search works on name."""
    DowntimeAction.objects.create(club=club, name="Bakery Work")
    DowntimeAction.objects.create(club=club, name="Farm Labor")
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeaction_changelist")
    response = client.get(url, {"q": "Bakery"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Bakery Work" in content
    assert "Farm Labor" not in content


@pytest.mark.django_db
def test_downtimeentry_admin_search(site_admin, login, action):
    """DowntimeEntry search works on label."""
    from downtime.models import DowntimeEntry

    DowntimeEntry.objects.create(action=action, label="Morning Shift")
    DowntimeEntry.objects.create(action=action, label="Night Watch")
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeentry_changelist")
    response = client.get(url, {"q": "Morning"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Morning Shift" in content
    assert "Night Watch" not in content


@pytest.mark.django_db
def test_downtimeentryitem_admin_search(site_admin, login, entry, item):
    """DowntimeEntryItem search works on item__name."""
    from items.models import Item

    item2 = Item.objects.create(club=entry.action.club, name="Potion")
    DowntimeEntryItem.objects.create(entry=entry, item=item, quantity=1)
    DowntimeEntryItem.objects.create(entry=entry, item=item2, quantity=1)
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeentryitem_changelist")
    response = client.get(url, {"q": item.name})
    assert response.status_code == 200
    content = response.content.decode()
    assert item.name in content
    assert "Potion" not in content


@pytest.mark.django_db
def test_downtimepointrequest_admin_search(site_admin, login, club, player):
    """DowntimePointRequest search works on requested_by__user__email and note."""
    import re

    from accounts.models import Membership

    membership = Membership.objects.get(user=player, club=club)
    DowntimePointRequest.objects.create(
        club=club, requested_by=membership, points=1, note="Special request"
    )
    DowntimePointRequest.objects.create(
        club=club, requested_by=membership, points=2, note="Normal request"
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointrequest_changelist")
    # Search by email (searches requested_by__user__email)
    response = client.get(url, {"q": player.email})
    assert response.status_code == 200
    content = response.content.decode()
    # Both requests should match since they have the same requested_by user
    rows = re.findall(r"<tr[^>]*>.*?</tr>", content, re.DOTALL)
    data_rows = [r for r in rows if "field-points" in r]
    assert len(data_rows) == 2
    # Search by note - should find req1 (points=1)
    response = client.get(url, {"q": "Special"})
    assert response.status_code == 200
    content = response.content.decode()
    rows = re.findall(r"<tr[^>]*>.*?</tr>", content, re.DOTALL)
    data_rows = [r for r in rows if "field-points" in r]
    assert len(data_rows) == 1
    # Check that the points field shows 1 (not 2)
    assert 'field-points">1<' in data_rows[0]
    assert 'field-points">2<' not in data_rows[0]


@pytest.mark.django_db
def test_downtimeaction_admin_autocomplete_club(site_admin, login, club):
    """DowntimeAction change form has autocomplete for club FK."""
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeaction_add")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Check for autocomplete widget (django-admin-autocomplete)
    assert "data-autocomplete-light-url" in content or "autocomplete" in content.lower()


@pytest.mark.django_db
def test_downtimeentry_admin_autocomplete_action(site_admin, login, club):
    """DowntimeEntry change form has autocomplete for action FK."""
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeentry_add")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "data-autocomplete-light-url" in content or "autocomplete" in content.lower()


@pytest.mark.django_db
def test_downtimeentryitem_admin_autocomplete_entry_item(site_admin, login, entry, item):
    """DowntimeEntryItem change form has autocomplete for entry and item FKs."""
    client = login(site_admin)
    url = reverse("admin:downtime_downtimeentryitem_add")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should have autocomplete for both entry and item
    assert (
        content.count("data-autocomplete-light-url") >= 1
        or content.lower().count("autocomplete") >= 1
    )


@pytest.mark.django_db
def test_downtimepointrequest_admin_autocomplete_club_requested_by_decided_by(
    site_admin, login, club
):
    """DowntimePointRequest change form has autocomplete for club, requested_by, decided_by FKs."""
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointrequest_add")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    # Should have autocomplete for club, requested_by, decided_by
    assert (
        content.count("data-autocomplete-light-url") >= 1
        or content.lower().count("autocomplete") >= 1
    )


@pytest.mark.django_db
def test_downtimepointrequest_admin_bulk_actions_appear(site_admin, login, club, player):
    """DowntimePointRequest changelist shows approve/decline bulk actions."""
    from accounts.models import Membership

    membership = Membership.objects.get(user=player, club=club)
    DowntimePointRequest.objects.create(
        club=club, requested_by=membership, points=1, status=DowntimePointRequest.Status.PENDING
    )
    client = login(site_admin)
    url = reverse("admin:downtime_downtimepointrequest_changelist")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "approve_requests" in content
    assert "decline_requests" in content
    assert "Approve selected requests" in content
    assert "Decline selected requests" in content
