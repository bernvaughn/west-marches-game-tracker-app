import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def directory(client, club):
    return client.get(reverse("characters:directory", args=[club.slug]))


@pytest.mark.story("U51")
def test_no_trades_column_or_propose_link(login, club, game_master):
    """Directory should never show a trades column or propose trade link."""
    body = directory(login(game_master), club).content.decode()
    assert "Trades with" not in body
    # Check that there's no propose trade URL in the body
    assert "trades:propose" not in body
    # Also check without a selected character
    body_no_select = directory(login(game_master), club).content.decode()
    assert "Trades with" not in body_no_select
    assert "trades:propose" not in body_no_select


@pytest.mark.story("U53")
def test_directory_name_link_styles(login, club, player, character, other_character):
    body = directory(login(player), club).content.decode()
    own = reverse("characters:detail", args=[club.slug, character.pk])
    assert f'<a href="{own}">{character.name}</a>' in body
    assert f"<span>{other_character.name}</span>" in body
    assert "wm-chip" not in body or f'href="{own}"' in body
    assert (
        body.count(f'href="{reverse("characters:detail", args=[club.slug, other_character.pk])}"')
        == 0
    )