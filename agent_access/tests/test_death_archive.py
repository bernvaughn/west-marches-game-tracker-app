"""Tests for agent access respecting dead and archived characters (story U146)."""

import datetime

import pytest
from django.urls import reverse

from accounts.models import Membership
from agent_access.models import ProposedBatch, ProposedLine
from agent_access.services.confirm import ConfirmError, confirm_batch
from agent_access.tokens import create_token
from ledger.models import LedgerEntry
from ledger.services import coin_balance
from player_characters.models import Character

pytestmark = [pytest.mark.story("U146"), pytest.mark.django_db]

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


@pytest.fixture
def dead_character(club, player):
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club, owner=owner, name="Dead Hero", died_on="2025-12-01", death_note="Fell in battle"
    )


@pytest.fixture
def archived_character(club, player):
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(
        club=club, owner=owner, name="Archived Hero", archived_at="2025-12-01T12:00:00Z"
    )


@pytest.fixture
def living_character(club, player):
    owner = Membership.objects.get(user=player, club=club)
    return Character.objects.create(club=club, owner=owner, name="Living Hero")


@pytest.fixture
def gm_connection(game_master, club):
    return create_token(game_master, club, "Test agent")


def sc(mcp, secret, tool, **arguments):
    status, result = mcp(secret, tool, **arguments)
    assert status == 200 and not result.get("isError")
    return result["structuredContent"]


# --- Lookup tests ---


def test_lookup_status_values(
    mcp, gm_connection, living_character, dead_character, archived_character
):
    _, secret = gm_connection
    # Default: archived excluded
    rows = sc(mcp, secret, "list_characters")["characters"]
    names = {r["name"] for r in rows}
    assert "Living Hero" in names
    assert "Dead Hero" in names
    assert "Archived Hero" not in names

    living = next(r for r in rows if r["name"] == "Living Hero")
    dead = next(r for r in rows if r["name"] == "Dead Hero")
    assert living["status"] == "living"
    assert living["died_on"] is None
    assert dead["status"] == "dead"
    assert dead["died_on"] == "2025-12-01"


def test_lookup_include_archived_shows_archived(mcp, gm_connection, archived_character):
    _, secret = gm_connection
    rows = sc(mcp, secret, "list_characters", include_archived=True)["characters"]
    archived = next(r for r in rows if r["name"] == "Archived Hero")
    assert archived["status"] == "archived"
    assert archived["died_on"] is None


def test_lookup_search_still_works(mcp, gm_connection, living_character, dead_character):
    _, secret = gm_connection
    rows = sc(mcp, secret, "list_characters", search="Living")["characters"]
    assert len(rows) == 1
    assert rows[0]["name"] == "Living Hero"


def test_lookup_other_club_not_leaked(mcp, gm_connection, other_club, other_player):
    _, secret = gm_connection
    other_owner = Membership.objects.create(user=other_player, club=other_club, is_game_master=True)
    Character.objects.create(club=other_club, owner=other_owner, name="Other Club Hero")
    rows = sc(mcp, secret, "list_characters")["characters"]
    assert "Other Club Hero" not in {r["name"] for r in rows}


# --- Propose tests ---


def test_propose_archived_line_accepted_and_flagged(
    mcp, gm_connection, archived_character, living_character, item
):
    _, secret = gm_connection
    lines = [
        {"character_id": living_character.pk, "coins_cp": 100, "note": "Living line"},
        {"character_id": archived_character.pk, "coins_cp": 200, "note": "Archived line"},
    ]
    res = sc(mcp, secret, "propose_awards", idempotency_key="k1", lines=lines)
    assert res["created"] is True
    # Check warnings
    assert len(res["warnings"]) == 1
    assert "Archived Hero is archived" in res["warnings"][0]
    # Check line data
    lines_data = res["lines"]
    living_line = next(
        line_data for line_data in lines_data if line_data["character_name"] == "Living Hero"
    )
    archived_line = next(
        line_data for line_data in lines_data if line_data["character_name"] == "Archived Hero"
    )
    assert living_line["character_status"] == "living"
    assert living_line["character_archived"] is False
    assert archived_line["character_status"] == "archived"
    assert archived_line["character_archived"] is True


def test_propose_dead_line_no_warning(mcp, gm_connection, dead_character, item):
    _, secret = gm_connection
    lines = [{"character_id": dead_character.pk, "coins_cp": 100, "note": "Dead line"}]
    res = sc(mcp, secret, "propose_awards", idempotency_key="k2", lines=lines)
    assert res["created"] is True
    assert res["warnings"] == []
    line = res["lines"][0]
    assert line["character_status"] == "dead"
    assert line["character_archived"] is False


# --- Confirm tests ---


def test_confirm_archived_line_refused_no_ledger(
    batch, club, game_master, archived_character, item
):
    # Replace the batch's line with one for an archived character
    batch.lines.all().delete()
    ProposedLine.objects.create(batch=batch, character=archived_character, coins=100)

    with pytest.raises(ConfirmError) as exc:
        confirm_batch(club=club, batch_id=batch.pk, actor=game_master)
    assert "is archived" in exc.value.messages[0]
    assert "Fix the line or confirm it" in exc.value.messages[0]
    assert not LedgerEntry.objects.filter(agent_batch=batch).exists()


def test_confirm_archived_line_with_confirm_archived(
    batch, club, game_master, archived_character, item
):
    batch.lines.all().delete()
    ProposedLine.objects.create(batch=batch, character=archived_character, coins=100)

    entries = confirm_batch(club=club, batch_id=batch.pk, actor=game_master, confirm_archived=True)
    assert len(entries) == 1
    assert coin_balance(archived_character) == 100
    batch.refresh_from_db()
    assert batch.status == "confirmed"


def test_confirm_fix_line_then_confirm_works(
    batch, club, game_master, archived_character, living_character, item
):
    batch.lines.all().delete()
    ProposedLine.objects.create(batch=batch, character=archived_character, coins=100)

    # First confirm fails
    with pytest.raises(ConfirmError):
        confirm_batch(club=club, batch_id=batch.pk, actor=game_master)

    # Fix the line to a living character
    line = batch.lines.first()
    line.character = living_character
    line.save()

    # Now confirm works
    entries = confirm_batch(club=club, batch_id=batch.pk, actor=game_master)
    assert len(entries) == 1
    assert coin_balance(living_character) == 100


def test_confirm_remove_archived_line_then_confirm(
    batch, club, game_master, archived_character, living_character, item
):
    batch.lines.all().delete()
    ProposedLine.objects.create(batch=batch, character=archived_character, coins=100)
    ProposedLine.objects.create(batch=batch, character=living_character, coins=50)

    # Remove the archived line
    archived_line = batch.lines.filter(character=archived_character).first()
    archived_line.delete()

    entries = confirm_batch(club=club, batch_id=batch.pk, actor=game_master)
    assert len(entries) == 1
    assert coin_balance(living_character) == 50


def test_confirm_dead_character_receives_award(batch, club, game_master, dead_character, item):
    batch.lines.all().delete()
    ProposedLine.objects.create(batch=batch, character=dead_character, coins=500)

    entries = confirm_batch(club=club, batch_id=batch.pk, actor=game_master)
    assert len(entries) == 1
    assert coin_balance(dead_character) == 500


# --- Form tests ---


def test_form_edit_onto_different_archived_character_rejected(
    batch, club, game_master, archived_character, living_character, item, gm_client
):
    batch.lines.all().delete()
    line = ProposedLine.objects.create(batch=batch, character=living_character, coins=100)

    # Try to edit to an archived character
    p = f"line-{line.pk}"
    data = {f"{p}-character": archived_character.pk, f"{p}-coins_cp": 100, f"{p}-note": "Test"}
    response = gm_client.post(
        reverse("agent_access:batch_line_edit", args=[club.slug, batch.pk, line.pk]), data
    )
    assert response.status_code == 400
    line.refresh_from_db()
    assert line.character == living_character


def test_form_edit_line_already_on_archived_character_works(
    batch, club, game_master, archived_character, item, gm_client
):
    batch.lines.all().delete()
    line = ProposedLine.objects.create(batch=batch, character=archived_character, coins=100)

    # Edit the line (same archived character) - should work
    p = f"line-{line.pk}"
    data = {f"{p}-character": archived_character.pk, f"{p}-coins_cp": 200, f"{p}-note": "Edited"}
    response = gm_client.post(
        reverse("agent_access:batch_line_edit", args=[club.slug, batch.pk, line.pk]), data
    )
    assert response.status_code == 302
    line.refresh_from_db()
    assert line.coins == 200
    assert line.character == archived_character


# --- Review page tests ---


def test_review_page_shows_warning_badge_checkbox_for_archived(
    batch, club, game_master, archived_character, living_character, gm_client
):
    batch.lines.all().delete()
    ProposedLine.objects.create(batch=batch, character=archived_character, coins=100)
    ProposedLine.objects.create(batch=batch, character=living_character, coins=50)

    url = reverse("agent_access:batch_detail", args=[club.slug, batch.pk])
    html = gm_client.get(url).content.decode()

    # Warning alert present
    assert "Archived characters" in html
    assert "held back until" in html
    # Archived badge present
    assert "Archived" in html
    # Checkbox present
    assert 'name="confirm_archived"' in html
    assert "Award anyway: these characters are archived" in html


def test_review_page_no_warning_for_clean_batch(
    batch, club, game_master, living_character, gm_client
):
    batch.lines.all().delete()
    ProposedLine.objects.create(batch=batch, character=living_character, coins=100)

    url = reverse("agent_access:batch_detail", args=[club.slug, batch.pk])
    html = gm_client.get(url).content.decode()

    # No warning alert
    assert "Archived characters" not in html
    # No checkbox
    assert 'name="confirm_archived"' not in html


def test_review_page_no_warning_for_confirmed_batch(
    batch, club, game_master, archived_character, gm_client
):
    batch.lines.all().delete()
    ProposedLine.objects.create(batch=batch, character=archived_character, coins=100)

    # Confirm the batch first
    confirm_batch(club=club, batch_id=batch.pk, actor=game_master, confirm_archived=True)

    url = reverse("agent_access:batch_detail", args=[club.slug, batch.pk])
    html = gm_client.get(url).content.decode()

    # No warning alert (batch is confirmed)
    assert "Archived characters" not in html
    # No checkbox
    assert 'name="confirm_archived"' not in html
