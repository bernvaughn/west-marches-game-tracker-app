import pytest
from django.contrib.messages import get_messages
from django.utils import timezone

from accounts.models import Membership, User
from agent_access.models import ProposedBatch
from agent_access.services.reversal import BatchNotReversible, reverse_batch
from ledger.models import LedgerEntry
from ledger.services import Line, coin_balance, item_quantities, record
from player_characters.models import Character

pytestmark = [pytest.mark.story("A6"), pytest.mark.django_db]


@pytest.fixture
def gm_client(login, game_master):
    return login(game_master)


@pytest.fixture
def character2(club, other_player):
    owner = Membership.objects.get(user=other_player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Bram")


def make_batch(club, connection, user, status, key="k1"):
    return ProposedBatch.objects.create(
        club=club,
        connection=connection,
        user=user,
        date=timezone.localdate(),
        idempotency_key=key,
        status=status,
        confirmed_at=timezone.now(),
        confirmed_by=user,
    )


@pytest.fixture
def confirmed_batch(club, gm_connection, game_master, character, character2, item):
    record(character, "award", [Line(coins=50)], actor=game_master)  # not in the batch
    batch = make_batch(club, gm_connection[0], game_master, ProposedBatch.Status.CONFIRMED)
    from ledger.services import record_many

    common = dict(kind="award", via_agent=True, agent_batch=batch, actor=game_master)
    record_many(
        [
            dict(character=character, lines=[Line(coins=500)], **common),
            dict(character=character2, lines=[Line(item=item, quantity=2)], **common),
            dict(character=character2, lines=[Line(coins=100)], **common),
        ]
    )
    return batch


def url(batch, club_slug="club-a"):
    return f"/c/{club_slug}/agent/batches/{batch.pk}/reverse/"


def count():
    return LedgerEntry.objects.count()


def msgs(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def test_reverse_writes_one_reversal_per_award(
    gm_client, confirmed_batch, character, character2, item, game_master
):
    before = count()
    resp = gm_client.post(url(confirmed_batch))
    assert resp.status_code == 302
    assert resp.url == f"/c/club-a/agent/batches/{confirmed_batch.pk}/"
    awards = LedgerEntry.objects.filter(agent_batch=confirmed_batch, kind="award")
    reversals = LedgerEntry.objects.filter(agent_batch=confirmed_batch, kind="reversal")
    assert awards.count() == 3 and reversals.count() == 3
    assert count() == before + 3
    for r in reversals:
        assert r.reverses in set(awards)
        assert r.via_agent is False
        assert r.created_by == game_master
        assert r.note == f"reversal of agent batch #{confirmed_batch.pk}"
        orig = {(ln.item_id, ln.quantity, ln.coins) for ln in r.reverses.lines.all()}
        neg = {(ln.item_id, -ln.quantity, -ln.coins) for ln in r.lines.all()}
        assert orig == neg
    assert coin_balance(character) == 50
    assert coin_balance(character2) == 0
    assert item_quantities(character2) == {}
    confirmed_batch.refresh_from_db()
    assert confirmed_batch.status == "reversed"
    assert confirmed_batch.reversed_at and confirmed_batch.reversed_by == game_master


def test_service_returns_entries(confirmed_batch, game_master):
    entries = reverse_batch(confirmed_batch, game_master)
    assert len(entries) == 3


def test_second_reverse_writes_nothing(gm_client, confirmed_batch):
    gm_client.post(url(confirmed_batch))
    n = count()
    resp = gm_client.post(url(confirmed_batch))
    assert count() == n
    assert any("confirmed" in m for m in msgs(resp))


def test_pending_batch_cannot_be_reversed(gm_client, club, gm_connection, game_master):
    batch = make_batch(club, gm_connection[0], game_master, ProposedBatch.Status.PENDING)
    gm_client.post(url(batch))
    assert count() == 0
    batch.refresh_from_db()
    assert batch.status == "pending"
    with pytest.raises(BatchNotReversible):
        reverse_batch(batch, game_master)


def test_spent_coins_block_reversal(gm_client, confirmed_batch, character, game_master):
    record(character, "purchase", [Line(coins=-500)], actor=game_master)
    n = count()
    resp = gm_client.post(url(confirmed_batch))
    assert count() == n
    confirmed_batch.refresh_from_db()
    assert confirmed_batch.status == "confirmed"
    assert any("available" in m for m in msgs(resp))


def test_spent_items_block_reversal(gm_client, confirmed_batch, character2, item, game_master):
    record(character2, "purchase", [Line(item=item, quantity=-2)], actor=game_master)
    n = count()
    resp = gm_client.post(url(confirmed_batch))
    assert count() == n
    confirmed_batch.refresh_from_db()
    assert confirmed_batch.status == "confirmed"
    assert any("available" in m for m in msgs(resp))


def test_get_not_allowed(gm_client, confirmed_batch):
    assert gm_client.get(url(confirmed_batch)).status_code == 405


def test_player_and_club_admin_refused(login, player, club_admin, confirmed_batch):
    n = count()
    for user in (player, club_admin):
        assert login(user).post(url(confirmed_batch)).status_code in (403, 404)
    assert count() == n


def test_other_club_gm_gets_404(login, other_club, confirmed_batch):
    gm = User.objects.create_user("gm3@example.com", password="pw", display_name="G3")
    Membership.objects.create(user=gm, club=other_club, is_game_master=True)
    n = count()
    assert login(gm).post(url(confirmed_batch)).status_code in (403, 404)
    assert login(gm).post(url(confirmed_batch, "club-b")).status_code == 404
    assert count() == n


def test_gm_cannot_reverse_other_club_batch(
    gm_client, other_club, other_club_gm_connection, game_master
):
    user = other_club_gm_connection[0].user
    batch = make_batch(
        other_club, other_club_gm_connection[0], user, ProposedBatch.Status.CONFIRMED
    )
    assert gm_client.post(url(batch)).status_code == 404
    batch.refresh_from_db()
    assert batch.status == "confirmed"
