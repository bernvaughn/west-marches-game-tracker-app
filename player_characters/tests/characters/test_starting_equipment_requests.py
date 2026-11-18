"""Tests for starting equipment request status display on character sheet."""

import pytest
from django.urls import reverse

from starting_equipment.models import StartingEquipmentRequest

pytestmark = [pytest.mark.django_db]


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def create_request(
    character, item, *, status="pending", quantity=1, note="", decided_by=None, decided_at=None
):
    return StartingEquipmentRequest.objects.create(
        club=character.club,
        character=character,
        item=item,
        quantity=quantity,
        note=note,
        status=status,
        decided_by=decided_by,
        decided_at=decided_at,
    )


class TestStartingEquipmentRequestsOnSheet:
    def test_context_includes_starting_requests(self, club, login, player, character, item):
        """DetailView context includes starting_requests queryset matching created requests."""
        req1 = create_request(character, item, note="Need for survival")
        req2 = create_request(character, item, status="approved", note="Approved by GM")

        client = login(player)
        response = client.get(detail_url(club, character))

        assert response.status_code == 200
        assert "starting_requests" in response.context
        requests = list(response.context["starting_requests"])
        assert len(requests) == 2
        assert req1 in requests
        assert req2 in requests

    def test_table_renders_item_quantity_note_and_status_badge(
        self, club, login, player, character, item
    ):
        """Table renders item name, quantity, note and status badge for each request."""
        create_request(character, item, quantity=2, note="Need for quest", status="pending")
        create_request(character, item, quantity=1, note="", status="approved")

        client = login(player)
        response = client.get(detail_url(club, character))

        assert response.status_code == 200
        content = response.content.decode()
        # Item name via _item_name.html includes the name
        assert item.name in content
        # Quantity
        assert "2" in content
        assert "1" in content
        # Note
        assert "Need for quest" in content
        # Status badges
        assert "Pending" in content
        assert "Approved" in content
        # Badge classes
        assert "wm-badge--info" in content
        assert "wm-badge--success" in content

    def test_empty_state_shows_when_no_requests(self, club, login, player, character):
        """Empty state text shows when the character has no requests."""
        client = login(player)
        response = client.get(detail_url(club, character))

        assert response.status_code == 200
        content = response.content.decode()
        assert "No magic starting item requests." in content

    def test_visible_to_player_game_master_club_admin_site_admin(
        self, club, login, player, game_master, club_admin, site_admin, character, item
    ):
        """Table visible to player, game master, club admin and site admin."""
        create_request(character, item, status="pending")

        for user in [player, game_master, club_admin, site_admin]:
            client = login(user)
            response = client.get(detail_url(club, character))
            assert response.status_code == 200, f"Failed for {user}"
            content = response.content.decode()
            assert "Magic starting item requests" in content
            assert item.name in content

    def test_not_visible_to_other_club_member(self, club, login, other_player, character, item):
        """Table not visible to another club member (can_view false)."""
        create_request(character, item, status="pending")

        client = login(other_player)
        response = client.get(detail_url(club, character))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Only the owner, game masters and club admins see this sheet." in content
        assert "Magic starting item requests" not in content

    def test_declined_status_shows_danger_badge(self, club, login, player, character, item):
        """Declined requests show danger badge."""
        create_request(character, item, status="declined", note="Not allowed")

        client = login(player)
        response = client.get(detail_url(club, character))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Declined" in content
        assert "wm-badge--danger" in content

    def test_decided_by_and_at_show_when_decided(
        self, club, login, player, game_master, character, item
    ):
        """Decided by/at shows when request has been decided."""
        from django.utils import timezone

        decided_at = timezone.now()
        create_request(
            character, item, status="approved", decided_by=game_master, decided_at=decided_at
        )

        client = login(player)
        response = client.get(detail_url(club, character))

        assert response.status_code == 200
        content = response.content.decode()
        assert game_master.display_name in content
        # Date format includes month name
        assert decided_at.strftime("%b") in content

    def test_order_by_created_descending(self, club, login, player, character, item):
        """Requests ordered by created descending (newest first)."""
        req1 = create_request(character, item, note="First")
        req2 = create_request(character, item, note="Second")
        req3 = create_request(character, item, note="Third")

        client = login(player)
        response = client.get(detail_url(club, character))

        assert response.status_code == 200
        requests = list(response.context["starting_requests"])
        assert requests[0] == req3
        assert requests[1] == req2
        assert requests[2] == req1
