import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def directory(client, club):
    return client.get(reverse("characters:directory", args=[club.slug]))


@pytest.mark.story("U53")
def test_directory_name_link_styles(login, club, player, character, other_character):
    body = directory(login(player), club).content.decode()
    own = reverse("characters:detail", args=[club.slug, character.pk])
    assert f'<a href="{own}">{character.name}</a>' in body
    assert f"<span>{other_character.name}</span>" in body
    assert not re.search(r"<a [^>]*wm-chip", body)
    assert (
        body.count(f'href="{reverse("characters:detail", args=[club.slug, other_character.pk])}"')
        == 0
    )
