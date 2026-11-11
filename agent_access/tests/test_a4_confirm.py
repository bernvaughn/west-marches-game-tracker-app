import datetime

import pytest
from django.urls import reverse

from accounts.models import Membership, User
from agent_access.models import ProposedBatch, ProposedItem, ProposedLine
from agent_access.services.confirm import ConfirmError, confirm_batch
from items.models import Item
from ledger.models import LedgerEntry
from ledger.services import coin_balance, item_quantities
from player_characters.models import Character

pytestmark = [pytest.mark.story("A4"), pytest.mark.django_db]

BATCH_DATE = datetime.date(2026, 5, 1)


@pytest.fixture
def gm_client(login, game_master):
    return login(game_master)


@pytest.fixture
def batch(club, game_master, gm_connection, character, item):
    b = ProposedBatch.objects.create(
        club=club,
        connection=gm_connection[0],
        user=game_master,
        date=BATCH_DATE,
        idempotency_key="k1",
        source_notes="Session notes",
    )
    ProposedLine.objects.create(batch=b, character=character, coins=250, note="Gold")
    ProposedLine.objects.create(batch=b, character=character, item=item, quantity=2)
    return b


def url(name, batch, *args):
    return reverse(f"agent_access:{name}", args=[batch.club.slug, batch.pk, *args])


def coin_post(prefix, cp=0, **extra):
    data = {f"{prefix}-coins_{s}": "" for s in ("pp", "gp", "sp", "cp")}
    data[f"{prefix}-coins_cp"] = str(cp)
    data.update(extra)
    return data


def test_confirm_writes_entries(batch, game_master, character, item, gm_client):
    response = gm_client.post(url("batch_confirm", batch))
    assert response.status_code == 302
    entries = list(LedgerEntry.objects.filter(agent_batch=batch).order_by("pk"))
    assert len(entries) == 2
    for e in entries:
        assert e.kind == "award" and e.via_agent and e.created_by == game_master
        assert e.note.endswith("recorded through an agent")
    assert entries[0].note == "Gold — recorded through an agent"
    assert entries[1].note == "recorded through an agent"
    assert entries[0].date == BATCH_DATE
    assert coin_balance(character) == 250
    assert item_quantities(character)[item.pk] == 2
    batch.refresh_from_db()
    assert batch.status == "confirmed"
    assert batch.confirmed_by == game_master and batch.confirmed_at


def test_edit_and_remove_then_confirm(batch, club, character, item, gm_client):
    coin_line, item_line = batch.lines.order_by("pk")
    p = f"line-{coin_line.pk}"
    data = coin_post(p, 300, **{f"{p}-character": character.pk, f"{p}-note": "Edited"})
    data[f"{p}-date"] = "2026-05-02"
    edit = reverse("agent_access:batch_line_edit", args=[club.slug, batch.pk, coin_line.pk])
    response = gm_client.post(edit, data)
    assert response.status_code == 302, response.context["rows"][0]["form"].errors
    coin_line.refresh_from_db()
    assert coin_line.coins == 300 and coin_line.note == "Edited"
    gm_client.post(
        reverse("agent_access:batch_line_remove", args=[club.slug, batch.pk, item_line.pk])
    )
    gm_client.post(url("batch_confirm", batch))
    (entry,) = LedgerEntry.objects.filter(agent_batch=batch)
    assert entry.date == datetime.date(2026, 5, 2)
    assert coin_balance(character) == 300
    assert not item_quantities(character)


def test_edit_other_club_ids_rejected(batch, club, other_club, gm_client):
    line = batch.lines.order_by("pk")[1]
    foreign_char = Character.objects.create(
        club=other_club,
        owner=Membership.objects.create(
            user=User.objects.create_user("x@example.com", password="pw", display_name="X"),
            club=other_club,
        ),
        name="Foreign",
    )
    foreign_item = Item.objects.create(club=other_club, name="Foreign", value_cp=1)
    p = f"line-{line.pk}"
    data = coin_post(
        p,
        0,
        **{f"{p}-character": foreign_char.pk, f"{p}-item": foreign_item.pk, f"{p}-quantity": 1},
    )
    response = gm_client.post(
        reverse("agent_access:batch_line_edit", args=[club.slug, batch.pk, line.pk]), data
    )
    assert response.status_code == 400
    line.refresh_from_db()
    assert line.character.club == club and line.item.club == club


def _proposed_line(batch, character, status, approved_item=None):
    proposed = ProposedItem.objects.create(
        club=batch.club, name="Mystery", status=status, approved_item=approved_item
    )
    batch.lines.all().delete()
    ProposedLine.objects.create(
        batch=batch, character=character, proposed_item=proposed, quantity=1
    )
    return proposed


def test_pending_proposed_item_refused_then_approved(batch, club, character, item, gm_client):
    proposed = _proposed_line(batch, character, "pending")
    with pytest.raises(ConfirmError) as exc:
        confirm_batch(club=club, batch_id=batch.pk, actor=batch.user)
    assert "Line 1" in exc.value.messages[0]
    assert not LedgerEntry.objects.filter(agent_batch=batch).exists()
    proposed.status, proposed.approved_item = "approved", item
    proposed.save()
    confirm_batch(club=club, batch_id=batch.pk, actor=batch.user)
    assert item_quantities(character)[item.pk] == 1


def test_rejected_retired_and_empty_refused(batch, club, character, item):
    proposed = _proposed_line(batch, character, "rejected")
    with pytest.raises(ConfirmError):
        confirm_batch(club=club, batch_id=batch.pk, actor=batch.user)
    proposed.status, proposed.approved_item = "approved", item
    proposed.save()
    item.retired = True
    item.save()
    with pytest.raises(ConfirmError) as exc:
        confirm_batch(club=club, batch_id=batch.pk, actor=batch.user)
    assert "retired" in exc.value.messages[0]
    batch.lines.all().delete()
    with pytest.raises(ConfirmError, match="empty"):
        confirm_batch(club=club, batch_id=batch.pk, actor=batch.user)


def test_double_confirm(batch, club, gm_client):
    gm_client.post(url("batch_confirm", batch))
    gm_client.post(url("batch_confirm", batch))
    assert LedgerEntry.objects.filter(agent_batch=batch).count() == 2
    with pytest.raises(ConfirmError):
        confirm_batch(club=club, batch_id=batch.pk, actor=batch.user)
    assert LedgerEntry.objects.filter(agent_batch=batch).count() == 2


def test_non_pending_not_editable(batch, club, gm_client):
    gm_client.post(url("batch_confirm", batch))
    line = batch.lines.first()
    gm_client.post(reverse("agent_access:batch_line_remove", args=[club.slug, batch.pk, line.pk]))
    gm_client.post(url("batch_discard", batch))
    assert batch.lines.count() == 2
    batch.refresh_from_db()
    assert batch.status == "confirmed"


def test_discard_and_list(batch, club, gm_client):
    page = gm_client.get(reverse("agent_access:batches", args=[club.slug]))
    assert page.status_code == 200 and f"#{batch.pk}" in page.content.decode()
    gm_client.post(url("batch_discard", batch))
    batch.refresh_from_db()
    assert batch.status == "discarded"


def test_player_forbidden(batch, login, player, club):
    c = login(player)
    assert c.get(reverse("agent_access:batches", args=[club.slug])).status_code in (403, 404)
    assert c.get(url("batch_detail", batch)).status_code in (403, 404)
    assert c.post(url("batch_confirm", batch)).status_code in (403, 404)
    batch.refresh_from_db()
    assert batch.status == "pending"


def test_other_club_gm_gets_404(batch, login, other_club_gm_connection):
    c = login(other_club_gm_connection[0].user)
    other = other_club_gm_connection[0].club
    line = batch.lines.first()
    for name, args in [
        ("batch_detail", []),
        ("batch_confirm", []),
        ("batch_line_edit", [line.pk]),
    ]:
        target = reverse(f"agent_access:{name}", args=[other.slug, batch.pk, *args])
        method = c.get if name == "batch_detail" else c.post
        assert method(target).status_code == 404
    batch.refresh_from_db()
    assert batch.status == "pending"


def test_script_escaped(batch, gm_client):
    batch.source_notes = "<script>alert(1)</script>"
    batch.save()
    line = batch.lines.first()
    line.note = "<script>alert(2)</script>"
    line.save()
    html = gm_client.get(url("batch_detail", batch)).content.decode()
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html


def test_confirmed_shows_reverse_form(batch, gm_client):
    gm_client.post(url("batch_confirm", batch))
    html = gm_client.get(url("batch_detail", batch)).content.decode()
    assert f'action="{url("batch_reverse", batch)}"' in html
