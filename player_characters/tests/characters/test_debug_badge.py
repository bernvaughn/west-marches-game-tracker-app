"""Debug test for badge rendering."""

import pytest
import re
from django.test import Client
from django.urls import reverse
from django.template.loader import render_to_string
from django.template import Template, Context

from accounts.models import Club, Membership, User
from character_options.services import seed_default_options
from player_characters.models import Character


@pytest.fixture
def club_with_options(db):
    club = Club.objects.create(name="Test Club", slug="test-club")
    seed_default_options(club)
    return club


@pytest.fixture
def player(db):
    return User.objects.create_user("player@example.com", password="pw", display_name="Player")


@pytest.fixture
def membership(club_with_options, player):
    return Membership.objects.create(user=player, club=club_with_options)


def test_detail_template_without_base(club_with_options, player, membership):
    """Test the detail template content without base.html extension."""
    character = Character.objects.create(
        club=club_with_options,
        owner=membership,
        name="TestChar",
        char_class="Custom Class",
        class_option=None,
    )
    
    # Read the detail template
    with open("player_characters/templates/player_characters/characters/detail.html") as f:
        template_content = f.read()
    
    # Remove the extends and block tags to test just the content
    # Find the content block
    import re
    content_match = re.search(r'{% block content %}(.*?){% endblock %}', template_content, re.DOTALL)
    if content_match:
        content = content_match.group(1)
    else:
        content = template_content
    
    # Remove the extends line
    content = re.sub(r'{% extends "base.html" %}', '', content)
    
    template = Template(content)
    
    context = Context({
        "character": character,
        "club": club_with_options,
        "owner_name": "Player",
        "can_view": True,
        "user": type('User', (), {"is_authenticated": True, "is_superuser": False})(),
        "club": club_with_options,
        "selected_character": character,
        "own_characters": [character],
        "APP_NAME": "Test",
        "APP_TAGLINE": "",
        "SITE_COPYRIGHT_YEAR": "2024",
        "flash_messages": "",
    })
    
    html = template.render(context)
    
    print(f"HEADER SECTION:")
    header_match = re.search(r'<header class="wm-sheet-header">(.*?)</header>', html, re.DOTALL)
    if header_match:
        print(header_match.group(1)[:500])
    
    # Check for badge marker
    if "BADGE-MARKER" in html:
        print("BADGE MARKER FOUND!")
    else:
        print("BADGE MARKER NOT FOUND")
        if header_match and "custom" in header_match.group(1).lower():
            print("custom text found in header")
        else:
            print("custom text NOT found in header")
    
    assert "BADGE-MARKER" in html