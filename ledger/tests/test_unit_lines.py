import pytest
from django.urls import reverse

from items.tests.factories import make_rope
from ledger.services import Line, record
from ledger.templatetags.coins import downtime_reward_text

pytestmark = [pytest.mark.django_db]


def index_url(club):
    return reverse("ledger:index", args=[club.slug])


def history_url(club, character):
    return reverse("ledger:character_history", args=[club.slug, character.pk])


def test_index_shows_unit_lines(login, game_master, club, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)], note="bundle")
    record(character, "consumed", [Line(item=rope, quantity=-10)], note="used")
    html = login(game_master).get(index_url(club)).content.decode()
    assert "+50 ft Rope" in html
    assert "-10 ft Rope" in html


def test_history_shows_unit_lines(login, player, club, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)], note="bundle")
    record(character, "consumed", [Line(item=rope, quantity=-10)], note="used")
    html = login(player).get(history_url(club, character)).content.decode()
    assert "+50 ft Rope" in html
    assert "-10 ft Rope" in html


def test_recent_changes_shows_unit_lines(login, player, club, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)], note="bundle")
    record(character, "consumed", [Line(item=rope, quantity=-10)], note="used")
    sheet = login(player).get(reverse("characters:detail", args=[club.slug, character.pk]))
    assert "+50 ft Rope" in sheet.content.decode()
    assert "-10 ft Rope" in sheet.content.decode()


def test_item_name_not_repeated(login, player, club, character, rope):
    record(character, "award", [Line(item=rope, quantity=50)])
    html = login(player).get(history_url(club, character)).content.decode()
    # Quantity part and item name appear once each: "+50 ft Rope", not "+50 ft Rope Rope".
    assert html.count("+50 ft Rope") == 1
    assert "+50 ft Rope Rope" not in html


def test_normal_item_unchanged(login, player, club, character, item):
    record(character, "award", [Line(item=item, quantity=3)])
    html = login(player).get(history_url(club, character)).content.decode()
    assert "+3 Rope" in html
    assert "+3 ft" not in html


def test_downtime_reward_text_stacked_and_normal(club, character, rope, item):
    entry = record(
        character,
        "award",
        [Line(coins=100), Line(item=rope, quantity=50), Line(item=item, quantity=3)],
    )
    text = downtime_reward_text(entry)
    assert "+50 ft Rope" in text
    assert "+3 Rope" in text


def test_downtime_reward_text_negative_stacked(club, character, rope):
    record(character, "award", [Line(item=rope, quantity=10)])
    entry = record(character, "consumed", [Line(item=rope, quantity=-10)])
    text = downtime_reward_text(entry)
    assert "-10 ft Rope" in text


@pytest.fixture
def rope(club):
    return make_rope(club)
