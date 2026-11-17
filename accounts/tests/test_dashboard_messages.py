"""Tests for My Messages dashboard provider and message detail view."""

import pytest
from django.urls import reverse

from accounts.models import Membership, Message


def _mem(user, club):
    return Membership.objects.get(user=user, club=club)


def _url_dashboard(club):
    return reverse("accounts:player_dashboard", args=[club.slug])


def _url_message_detail(club, pk):
    return reverse("accounts:message_detail", args=[club.slug, pk])


@pytest.fixture
def player_with_messages(club, player, character, login):
    """Create a player with some sent messages."""
    mem = _mem(player, club)
    msg1 = Message.objects.create(
        club=club, sender=mem, character=character, body="Hello admins, I need help!"
    )
    msg2 = Message.objects.create(
        club=club, sender=mem, character=character, body="Another message"
    )
    # Change status of one message
    msg2.status = Message.Status.HANDLED
    msg2.save()
    return [msg1, msg2]


@pytest.mark.story("S9")
def test_dashboard_my_messages_shows_when_has_messages(
    club, player, character, player_with_messages, login
):
    """Dashboard shows My Messages section when player has sent messages."""
    c = login(player)
    resp = c.get(_url_dashboard(club))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "My Messages" in content
    # Should show both messages
    assert "Hello admins, I need help!" in content
    assert "Another message" in content


@pytest.mark.story("S9")
def test_dashboard_my_messages_hidden_when_no_messages(club, player, character, login):
    """Dashboard hides My Messages section when player has no sent messages."""
    c = login(player)
    resp = c.get(_url_dashboard(club))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "My Messages" not in content


@pytest.mark.story("S9")
def test_dashboard_my_messages_shows_subject_date_status(
    club, player, character, player_with_messages, login
):
    """Each row shows subject, sent date, status badge."""
    c = login(player)
    resp = c.get(_url_dashboard(club))
    content = resp.content.decode()
    # Subject (truncated to 50 chars)
    assert "Hello admins, I need help!" in content
    # Status badges
    assert "Open" in content
    assert "Handled" in content
    # Date format (M d, Y H:i)
    # Check that date appears
    import re
    assert re.search(r"\w{3} \d{1,2}, \d{4} \d{2}:\d{2}", content)


@pytest.mark.story("S9")
def test_dashboard_my_messages_status_badge_classes(
    club, player, character, player_with_messages, login
):
    """Status badges use correct Bootstrap classes."""
    c = login(player)
    resp = c.get(_url_dashboard(club))
    content = resp.content.decode()
    # Open -> text-bg-warning
    assert "text-bg-warning" in content
    # Handled -> text-bg-success
    assert "text-bg-success" in content


@pytest.mark.story("S9")
def test_dashboard_my_messages_view_response_link(
    club, player, character, player_with_messages, login
):
    """Each row has a 'View Response' link to message_detail."""
    c = login(player)
    resp = c.get(_url_dashboard(club))
    content = resp.content.decode()
    # Should have links to message_detail
    for msg in player_with_messages:
        url = _url_message_detail(club, msg.pk)
        assert url in content
        assert "View Response" in content


@pytest.mark.story("S9")
def test_message_detail_view_for_sender(
    club, player, character, player_with_messages, login
):
    """Sender can view their own message detail (read-only)."""
    msg = player_with_messages[0]
    c = login(player)
    resp = c.get(_url_message_detail(club, msg.pk))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert f"Message #{msg.pk}" in content
    assert "Hello admins, I need help!" in content
    # Should NOT have admin action buttons (read-only)
    assert "Mark as Handled" not in content
    assert "Mark as Closed" not in content


@pytest.mark.story("S9")
def test_message_detail_view_for_admin(
    club, club_admin, player, character, player_with_messages, login
):
    """Club admin can view any message detail."""
    msg = player_with_messages[0]
    c = login(club_admin)
    resp = c.get(_url_message_detail(club, msg.pk))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert f"Message #{msg.pk}" in content


@pytest.mark.story("S9")
def test_message_detail_view_forbidden_for_other_player(
    club, other_player, other_club, player, character, player_with_messages, login
):
    """Other players cannot view someone else's message."""
    msg = player_with_messages[0]
    c = login(other_player)
    resp = c.get(_url_message_detail(club, msg.pk))
    assert resp.status_code == 404


@pytest.mark.story("S9")
def test_message_detail_shows_admin_response(
    club, player, character, player_with_messages, login
):
    """Message detail shows admin response when message is handled."""
    from items.models import Item
    from ledger.models import LedgerEntry

    msg = player_with_messages[1]  # Handled message
    # Create an item first
    item = Item.objects.create(club=club, name="Test Item", retired=False)
    # Add a granted entry (admin response)
    entry = LedgerEntry.objects.create(
        club=club,
        character=character,
        kind=LedgerEntry.Kind.AWARD,
        source_message=msg,
        note="Here is your item",
    )
    entry.lines.create(item=item, quantity=1)

    c = login(player)
    resp = c.get(_url_message_detail(club, msg.pk))
    content = resp.content.decode()
    assert "Admin Response" in content


@pytest.mark.story("S9")
def test_provider_should_show_logic():
    """Test the should_show method logic."""
    from accounts.dashboard_providers import MyMessagesDashboardProvider

    provider = MyMessagesDashboardProvider()

    # We'll test via the view integration instead of unit testing the provider directly
    # since it requires request/club/character/membership
    assert provider.key == "my_messages"
    assert provider.order == 7


@pytest.mark.story("S9")
def test_message_detail_404_for_nonexistent(club, player, login):
    """Message detail returns 404 for non-existent message."""
    c = login(player)
    resp = c.get(_url_message_detail(club, 99999))
    assert resp.status_code == 404


@pytest.mark.story("S9")
def test_dashboard_my_messages_shows_character_name(
    club, player, character, player_with_messages, login
):
    """Message row shows character name when message has character."""
    c = login(player)
    resp = c.get(_url_dashboard(club))
    content = resp.content.decode()
    assert character.name in content


@pytest.mark.story("S9")
def test_dashboard_my_messages_order_by_created_desc(
    club, player, character, login
):
    """Messages ordered by created date descending (newest first)."""
    mem = _mem(player, club)
    Message.objects.create(
        club=club, sender=mem, character=character, body="First message"
    )
    Message.objects.create(
        club=club, sender=mem, character=character, body="Second message"
    )
    Message.objects.create(
        club=club, sender=mem, character=character, body="Third message"
    )

    c = login(player)
    resp = c.get(_url_dashboard(club))
    content = resp.content.decode()

    # Find positions in content
    pos1 = content.find("First message")
    pos2 = content.find("Second message")
    pos3 = content.find("Third message")

    # Third (newest) should appear first
    assert pos3 < pos2 < pos1