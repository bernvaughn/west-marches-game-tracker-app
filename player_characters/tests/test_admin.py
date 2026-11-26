"""Test player_characters admin changelists and change forms."""

import pytest
from django.urls import reverse

from accounts.models import Membership, User
from items.models import Item
from player_characters.models import Character, ItemNote, JunkMark, SelectedCharacter


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


@pytest.mark.django_db
def test_selectedcharacter_admin_list_filter_club(site_admin, login, club, other_club, player):
    """SelectedCharacter changelist filters by club via membership__club."""
    membership = player.memberships.get(club=club)
    character = membership.characters.create(club=club, name="Char A")
    SelectedCharacter.objects.create(membership=membership, character=character)

    other_user = User.objects.create_user("other@example.com", password="pw", display_name="Other")
    other_membership = Membership.objects.create(user=other_user, club=other_club)
    other_character = Character.objects.create(
        club=other_club, owner=other_membership, name="Char B"
    )
    SelectedCharacter.objects.create(membership=other_membership, character=other_character)

    client = login(site_admin)
    url = reverse("admin:player_characters_selectedcharacter_changelist")
    response = client.get(url, {"membership__club": club.pk})
    assert response.status_code == 200
    assert b"Char A" in response.content
    assert b"Char B" not in response.content


@pytest.mark.django_db
def test_selectedcharacter_admin_search(site_admin, login, club, player, other_player):
    """SelectedCharacter changelist search works on character__name."""
    membership = player.memberships.get(club=club)
    character = membership.characters.create(club=club, name="UniqueCharacter")
    SelectedCharacter.objects.create(membership=membership, character=character)

    other_membership = other_player.memberships.get(club=club)
    other_character = other_membership.characters.create(club=club, name="Other Character")
    SelectedCharacter.objects.create(membership=other_membership, character=other_character)

    client = login(site_admin)
    url = reverse("admin:player_characters_selectedcharacter_changelist")
    response = client.get(url, {"q": "UniqueCharacter"})
    assert response.status_code == 200
    assert b"UniqueCharacter" in response.content
    assert b"Other Character" not in response.content


@pytest.mark.django_db
def test_selectedcharacter_admin_autocomplete(site_admin, login, club, player):
    """SelectedCharacter change form renders autocomplete widgets for FKs."""
    membership = player.memberships.get(club=club)
    character = membership.characters.create(club=club, name="Test Character")
    sc = SelectedCharacter.objects.create(membership=membership, character=character)
    client = login(site_admin)
    url = reverse("admin:player_characters_selectedcharacter_change", args=[sc.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-field-name="membership"' in content
    assert 'data-field-name="character"' in content
    assert "admin-autocomplete" in content


@pytest.mark.django_db
def test_junkmark_admin_list_display(site_admin, login, club, character, item):
    """JunkMark changelist shows character, item, quantity."""
    JunkMark.objects.create(character=character, item=item, quantity=7)
    client = login(site_admin)
    response = client.get(reverse("admin:player_characters_junkmark_changelist"))
    assert response.status_code == 200
    assert character.name.encode() in response.content
    assert item.name.encode() in response.content
    assert b"7" in response.content


@pytest.mark.django_db
def test_junkmark_admin_list_filter_club(site_admin, login, club, other_club, character, item):
    """JunkMark changelist filters by club via character__club."""
    JunkMark.objects.create(character=character, item=item, quantity=3)

    other_user = User.objects.create_user(
        "other2@example.com", password="pw", display_name="Other2"
    )
    other_membership = Membership.objects.create(user=other_user, club=other_club)
    other_character = Character.objects.create(
        club=other_club, owner=other_membership, name="Other Char"
    )
    other_item = Item.objects.create(club=other_club, name="Other Item", value_cp=100)
    JunkMark.objects.create(character=other_character, item=other_item, quantity=5)

    client = login(site_admin)
    url = reverse("admin:player_characters_junkmark_changelist")
    response = client.get(url, {"character__club": club.pk})
    assert response.status_code == 200
    assert item.name.encode() in response.content
    assert b"Other Item" not in response.content


@pytest.mark.django_db
def test_junkmark_admin_search(site_admin, login, club, character, item):
    """JunkMark changelist search works on item__name."""
    JunkMark.objects.create(character=character, item=item, quantity=3)

    other_item = Item.objects.create(club=club, name="Unique Item", value_cp=100)
    JunkMark.objects.create(character=character, item=other_item, quantity=5)

    client = login(site_admin)
    url = reverse("admin:player_characters_junkmark_changelist")
    response = client.get(url, {"q": "Rope"})
    assert response.status_code == 200
    assert item.name.encode() in response.content
    assert b"Unique Item" not in response.content


@pytest.mark.django_db
def test_junkmark_admin_autocomplete(site_admin, login, club, character, item):
    """JunkMark change form renders autocomplete widgets for FKs."""
    jm = JunkMark.objects.create(character=character, item=item, quantity=3)
    client = login(site_admin)
    url = reverse("admin:player_characters_junkmark_change", args=[jm.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-field-name="character"' in content
    assert 'data-field-name="item"' in content
    assert "admin-autocomplete" in content


@pytest.mark.django_db
def test_itemnote_admin_list_display(site_admin, login, club, character, item):
    """ItemNote changelist shows character, item, truncated text."""
    ItemNote.objects.create(
        character=character, item=item, text="This is a test note for the item."
    )
    client = login(site_admin)
    response = client.get(reverse("admin:player_characters_itemnote_changelist"))
    assert response.status_code == 200
    assert character.name.encode() in response.content
    assert item.name.encode() in response.content


@pytest.mark.django_db
def test_itemnote_admin_list_filter_club(site_admin, login, club, other_club, character, item):
    """ItemNote changelist filters by club via character__club."""
    ItemNote.objects.create(character=character, item=item, text="Note one")

    other_user = User.objects.create_user(
        "other3@example.com", password="pw", display_name="Other3"
    )
    other_membership = Membership.objects.create(user=other_user, club=other_club)
    other_character = Character.objects.create(
        club=other_club, owner=other_membership, name="Other Char"
    )
    ItemNote.objects.create(character=other_character, item=item, text="Note two")

    client = login(site_admin)
    url = reverse("admin:player_characters_itemnote_changelist")
    response = client.get(url, {"character__club": club.pk})
    assert response.status_code == 200
    assert b"Note one" in response.content
    assert b"Note two" not in response.content


@pytest.mark.django_db
def test_itemnote_admin_search(site_admin, login, club, character, item):
    """ItemNote changelist search works on text."""
    ItemNote.objects.create(character=character, item=item, text="Unique note text")

    other_item = Item.objects.create(club=club, name="Other Item", value_cp=100)
    ItemNote.objects.create(character=character, item=other_item, text="Other note")

    client = login(site_admin)
    url = reverse("admin:player_characters_itemnote_changelist")
    response = client.get(url, {"q": "Unique note text"})
    assert response.status_code == 200
    assert b"Unique note text" in response.content
    assert b"Other note" not in response.content


@pytest.mark.django_db
def test_itemnote_admin_autocomplete(site_admin, login, club, character, item):
    """ItemNote change form renders autocomplete widgets for FKs."""
    note = ItemNote.objects.create(character=character, item=item, text="Note")
    client = login(site_admin)
    url = reverse("admin:player_characters_itemnote_change", args=[note.pk])
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-field-name="character"' in content
    assert 'data-field-name="item"' in content
    assert "admin-autocomplete" in content
