import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import Membership
from items.models import Item
from items.usage import ownership_counts
from ledger.services import Line, record
from player_characters.models import Character

pytestmark = [pytest.mark.story("U74"), pytest.mark.django_db]


def index(club):
    return reverse("items:index", args=[club.slug])


@pytest.fixture
def second(club, other_player):
    return Character.objects.create(
        club=club, owner=Membership.objects.get(user=other_player, club=club), name="Borin"
    )


def test_counts_per_item(club, item, character, second):
    record(character, "award", [Line(item=item, quantity=2)])
    record(second, "award", [Line(item=item, quantity=3)])
    record(second, "award", [Line(item=item, quantity=-1)])
    own = ownership_counts(club)[item.pk]
    assert (own.characters, own.held) == (2, 4)


def test_zero_total_not_counted_and_absent(club, item, character, second):
    record(character, "award", [Line(item=item, quantity=2)])
    record(character, "award", [Line(item=item, quantity=-2)])
    assert item.pk not in ownership_counts(club)


def test_retired_items_counted(club, character):
    old = Item.objects.create(club=club, name="Old", retired=True)
    record(character, "award", [Line(item=old, quantity=1)])
    assert ownership_counts(club)[old.pk].held == 1


def test_other_club_not_counted(club, other_club, item):
    other_item = Item.objects.create(club=other_club, name="Foreign")
    owner = Membership.objects.create(
        user=__import__("accounts.models", fromlist=["User"]).User.objects.create_user(
            "x@example.com", password="pw", display_name="X"
        ),
        club=other_club,
    )
    ch = Character.objects.create(club=other_club, owner=owner, name="Zed")
    record(ch, "award", [Line(item=other_item, quantity=5)])
    assert ownership_counts(club) == {}
    assert ownership_counts(other_club)[other_item.pk].held == 5


def test_one_query(club, item, character, second):
    record(character, "award", [Line(item=item, quantity=2)])
    record(second, "award", [Line(item=item, quantity=2)])
    with CaptureQueriesContext(connection) as ctx:
        ownership_counts(club)
    assert len(ctx) == 1


def test_admin_and_gm_see_columns_players_do_not(
    login, club, item, character, club_admin, game_master, player
):
    record(character, "award", [Line(item=item, quantity=2)])
    for u in (club_admin, game_master):
        r = login(u).get(index(club))
        assert b"Characters" in r.content and b"Held" in r.content
    r = login(player).get(index(club))
    assert b"Characters" not in r.content and b"Held" not in r.content
