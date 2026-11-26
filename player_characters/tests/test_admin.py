"""Test player_characters admin changelists and change forms."""

import pytest
from django.urls import reverse

from player_characters.models import ItemNote, JunkMark, SelectedCharacter


@pytest.mark.django_db
def test_selectedcharacter_admin_changelist_and_change(site_admin, login, club, player):
    """SelectedCharacter changelist and change form load."""
    membership = player.memberships.get(club=club)
    character = membership.characters.create(club=club, name="Test Character")

    sc = SelectedCharacter.objects.create(membership=membership, character=character)
    client = login(site_admin)

    # Changelist
    url = reverse("admin:player_characters_selectedcharacter_changelist")
    response = client.get(url)
    assert response.status_code == 200
    # list_display shows membership.__str__ ("Player @ Club A") and character.name
    assert b"Player @ Club A" in response.content
    assert b"Test Character" in response.content

    # Change form
    url = reverse("admin:player_characters_selectedcharacter_change", args=[sc.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert b"Player @ Club A" in response.content
    assert b"Test Character" in response.content


@pytest.mark.django_db
def test_junkmark_admin_changelist_and_change(site_admin, login, club, player, character, item):
    """JunkMark changelist and change form load."""
    jm = JunkMark.objects.create(character=character, item=item, quantity=3)
    client = login(site_admin)

    # Changelist
    response = client.get(reverse("admin:player_characters_junkmark_changelist"))
    assert response.status_code == 200
    assert character.name.encode() in response.content
    assert item.name.encode() in response.content
    assert b"3" in response.content

    # Change form
    url = reverse("admin:player_characters_junkmark_change", args=[jm.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert character.name.encode() in response.content
    assert item.name.encode() in response.content
    assert b"3" in response.content


@pytest.mark.django_db
def test_itemnote_admin_changelist_and_change(site_admin, login, club, player, character, item):
    """ItemNote changelist and change form load."""
    note_text = "This is a test note for the item."
    note = ItemNote.objects.create(character=character, item=item, text=note_text)
    client = login(site_admin)

    # Changelist
    response = client.get(reverse("admin:player_characters_itemnote_changelist"))
    assert response.status_code == 200
    assert character.name.encode() in response.content
    assert item.name.encode() in response.content
    assert note_text.encode() in response.content

    # Change form
    url = reverse("admin:player_characters_itemnote_change", args=[note.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert character.name.encode() in response.content
    assert item.name.encode() in response.content
    assert note_text.encode() in response.content

    # Text field should be readonly (no save buttons for text field)
    content = response.content.decode()
    assert "readonly" in content.lower() or "disabled" in content.lower()


@pytest.mark.django_db
def test_itemnote_truncated_text_in_changelist(site_admin, login, club, player, character, item):
    """ItemNote truncated_text shows truncated text in changelist."""
    long_text = "A" * 60
    ItemNote.objects.create(character=character, item=item, text=long_text)
    client = login(site_admin)

    response = client.get(reverse("admin:player_characters_itemnote_changelist"))
    assert response.status_code == 200
    content = response.content.decode()
    # Should show truncated version (47 chars + ...)
    assert "A" * 47 + "..." in content
    # Should not show full text
    assert long_text not in content
