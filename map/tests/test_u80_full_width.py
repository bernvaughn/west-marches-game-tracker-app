import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.story("U80")
def test_map_detail_is_full_width(club, login, game_master, hex_map):
    url = reverse("map:detail", args=[club.slug, hex_map.pk])
    html = login(game_master).get(url).content.decode()
    assert 'class="wm-main wm-main--full"' in html
