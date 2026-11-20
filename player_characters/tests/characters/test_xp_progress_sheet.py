"""View tests for XP progress on the character detail sheet."""

import pytest
from django.conf import settings
from django.urls import reverse

from player_characters.models import Character

pytestmark = [pytest.mark.django_db]


def detail_url(club, character):
    return reverse("characters:detail", kwargs={"club_slug": club.slug, "pk": character.pk})


def edit_url(club, character):
    return reverse("characters:edit", kwargs={"club_slug": club.slug, "pk": character.pk})


def _set(character, **fields):
    Character.objects.filter(pk=character.pk).update(**fields)
    character.refresh_from_db()


def test_level_5_with_6500_xp_shows_bar_toward_level_6(club, login, player, character):
    _set(character, level=5, xp=6500)
    content = login(player).get(detail_url(club, character)).content.decode()
    assert "6,500 / 14,000 XP to level 6" in content
    assert 'role="progressbar"' in content
    assert 'aria-label="XP progress toward level 6"' in content
    assert "Level up ready" not in content


def test_level_4_with_6500_xp_shows_level_up_ready_badge(club, login, player, character):
    _set(character, level=4, xp=6500)
    content = login(player).get(detail_url(club, character)).content.decode()
    assert "Level up ready" in content
    assert f'href="{edit_url(club, character)}"' in content
    assert f'class="no-print" href="{edit_url(club, character)}"' in content


def test_level_4_with_6499_xp_shows_no_badge(club, login, player, character):
    _set(character, level=4, xp=6499)
    content = login(player).get(detail_url(club, character)).content.decode()
    assert "Level up ready" not in content
    assert "6,499 / 6,500 XP to level 5" in content


def test_level_20_shows_max_level(club, login, player, character):
    _set(character, level=20, xp=355000)
    content = login(player).get(detail_url(club, character)).content.decode()
    assert "Max level" in content
    assert 'role="progressbar"' not in content


def test_blank_xp_shows_nothing_new(club, login, player, character):
    _set(character, level=5, xp=None)
    content = login(player).get(detail_url(club, character)).content.decode()
    assert "XP to level" not in content
    assert 'role="progressbar"' not in content
    assert "Level up ready" not in content
    assert "&mdash;" in content


def test_blank_level_with_xp_shows_bar_no_badge(club, login, player, character):
    _set(character, level=None, xp=6500)
    content = login(player).get(detail_url(club, character)).content.decode()
    assert "6,500 / 14,000 XP to level 6" in content
    assert 'role="progressbar"' in content
    assert "Level up ready" not in content


def test_other_player_sees_no_xp_text(club, login, player, other_player, character):
    _set(character, level=5, xp=6500)
    content = login(other_player).get(detail_url(club, character)).content.decode()
    assert "Only the owner" in content
    assert "XP to level" not in content
    assert 'role="progressbar"' not in content


def test_bar_and_badge_carry_print_hidden_classes(club, login, player, character):
    _set(character, level=4, xp=6500)
    content = login(player).get(detail_url(club, character)).content.decode()
    assert 'class="wm-xp-bar"' in content
    assert f'class="no-print" href="{edit_url(club, character)}"' in content


def test_print_css_hides_bar_and_keeps_text():
    path = settings.BASE_DIR / "static" / "css" / "areas" / "characters.css"
    css = path.read_text()
    start = css.index("@media print {")
    # The closing brace of the block sits alone on its line; inner rules end
    # with "; }" followed by indented lines, so "\n}" marks the block end.
    end = css.index("\n}", start)
    block = css[start : end + 2]
    assert ".wm-xp-bar { display: none; }" in block
    assert ".wm-xp-text { color: black; }" in block
