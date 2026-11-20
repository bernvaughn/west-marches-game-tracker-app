import pytest
from django.contrib.messages import get_messages
from django.db import IntegrityError
from django.urls import reverse

from ledger.models import LedgerEntry
from ledger.services import Line, record
from player_characters.models import ItemNote
from player_characters.notes import NoteError, set_note

pytestmark = [pytest.mark.story("U122"), pytest.mark.django_db]


@pytest.fixture
def owned(character, item):
    record(character, "award", [Line(item=item, quantity=5), Line(coins=100)])
    return character


def note_url(club, character, item):
    return reverse("characters:note", args=[club.slug, character.pk, item.pk])


def sheet_url(club, character):
    return reverse("characters:detail", args=[club.slug, character.pk])


def flash_messages(response):
    """Return the list of flash message strings queued on the response's request."""
    return [str(m) for m in get_messages(response.wsgi_request)]


# --- permissions ----------------------------------------------------------


def test_owner_can_get_and_post(club, login, player, owned, item):
    c = login(player)
    assert c.get(note_url(club, owned, item)).status_code == 200
    r = c.post(note_url(club, owned, item), {"text": "A handy rope."})
    assert r.status_code == 302
    assert r["Location"] == sheet_url(club, owned)
    note = ItemNote.objects.get(character=owned, item=item)
    assert note.text == "A handy rope."


def test_htmx_post_redirects(club, login, player, owned, item):
    c = login(player)
    r = c.post(note_url(club, owned, item), {"text": "Htmx note."}, HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    assert r["HX-Redirect"] == sheet_url(club, owned)


@pytest.mark.parametrize("who", ["game_master", "club_admin", "site_admin", "other_player"])
def test_non_owner_cannot_edit(club, login, request, owned, item, who):
    c = login(request.getfixturevalue(who))
    assert c.post(note_url(club, owned, item), {"text": "Trying."}).status_code == 403
    assert ItemNote.objects.count() == 0


def test_anonymous_cannot_edit(club, client, owned, item):
    assert client.post(note_url(club, owned, item), {"text": "Trying."}).status_code == 302


def test_other_club_item_is_404(club, login, player, owned, item, foreign_member):
    c = login(foreign_member)
    assert c.get(note_url(club, owned, item)).status_code == 404


def test_404_when_character_owns_none(club, login, player, character, item):
    c = login(player)
    assert c.get(note_url(club, character, item)).status_code == 404


# --- reading on the sheet -------------------------------------------------


def test_sheet_shows_note_title_to_owner(club, login, player, owned, item):
    set_note(owned, item, "Do not lose this.\nKeep it dry.", player)
    body = login(player).get(sheet_url(club, owned)).content.decode()
    assert 'title="Do not lose this."' in body
    assert 'aria-label="Edit note"' in body
    # owner sees the icon only, not the full inline text
    assert "Keep it dry." not in body


def test_owner_sees_add_note_button_without_a_note(club, login, player, owned, item):
    # Regression: the owner must be able to add a first note from the sheet.
    body = login(player).get(sheet_url(club, owned)).content.decode()
    assert f'href="{note_url(club, owned, item)}"' in body
    assert 'aria-label="Add note"' in body
    assert 'title="Add your own note about this item."' in body


@pytest.mark.parametrize("who", ["game_master", "club_admin"])
def test_non_owner_viewer_sees_no_note_button(club, login, request, player, owned, item, who):
    body = login(request.getfixturevalue(who)).get(sheet_url(club, owned)).content.decode()
    assert note_url(club, owned, item) not in body
    set_note(owned, item, "Read only.", player)
    body = login(request.getfixturevalue(who)).get(sheet_url(club, owned)).content.decode()
    assert note_url(club, owned, item) not in body
    assert "Read only." in body


def test_sheet_shows_inline_note_to_gm_and_club_admin(club, login, request, player, owned, item):
    set_note(owned, item, "Do not lose this.", player)
    for who in ("game_master", "club_admin"):
        body = login(request.getfixturevalue(who)).get(sheet_url(club, owned)).content.decode()
        assert "Do not lose this." in body


def test_other_player_sees_nothing(club, login, other_player, player, owned, item):
    set_note(owned, item, "Secret.", player)
    r = login(other_player).get(sheet_url(club, owned))
    assert r.status_code == 200
    assert "Secret." not in r.content.decode()


def test_note_isolation_between_characters(club, login, player, owned, item, second_character):
    record(second_character, "award", [Line(item=item, quantity=1)])
    set_note(owned, item, "Aria's note.", player)
    body = login(player).get(sheet_url(club, second_character)).content.decode()
    assert "Aria's note." not in body


def test_cross_club_sheet_blocked(club, login, player, owned, item, foreign_character):
    assert login(player).get(sheet_url(club, foreign_character)).status_code == 404


# --- length ---------------------------------------------------------------


def test_thousand_characters_saves(club, login, player, owned, item):
    c = login(player)
    text = "x" * 1000
    r = c.post(note_url(club, owned, item), {"text": text})
    assert r.status_code == 302
    assert ItemNote.objects.get(character=owned, item=item).text == text


def test_thousand_characters_with_newlines_saves(club, login, player, owned, item):
    c = login(player)
    text = ("ab\n" * 249) + "ab"  # 1,000 characters, newlines kept, no trailing newline
    r = c.post(note_url(club, owned, item), {"text": text})
    assert r.status_code == 302
    assert ItemNote.objects.get(character=owned, item=item).text == text


def test_crlf_is_normalised(club, login, player, owned, item):
    c = login(player)
    c.post(note_url(club, owned, item), {"text": "line1\r\nline2\r\n"})
    assert ItemNote.objects.get(character=owned, item=item).text == "line1\nline2"


def test_one_thousand_and_one_is_refused(club, login, player, owned, item):
    c = login(player)
    r = c.post(note_url(club, owned, item), {"text": "x" * 1001})
    assert r.status_code == 200
    assert ItemNote.objects.count() == 0
    assert "at most 1000 characters" in r.content.decode()


def test_set_note_raises_over_limit(owned, item, player):
    with pytest.raises(NoteError):
        set_note(owned, item, "x" * 1001, player)


# --- clear ----------------------------------------------------------------


def test_clearing_deletes_row(club, login, player, owned, item):
    set_note(owned, item, "A note.", player)
    assert ItemNote.objects.count() == 1
    c = login(player)
    r = c.post(note_url(club, owned, item), {"text": "   "})
    assert r.status_code == 302
    assert ItemNote.objects.count() == 0
    assert any("Cleared note" in m for m in flash_messages(r))


def test_whitespace_only_clears(club, login, player, owned, item):
    set_note(owned, item, "A note.", player)
    c = login(player)
    c.post(note_url(club, owned, item), {"text": "\t\n "})
    assert ItemNote.objects.count() == 0


# --- plain text -----------------------------------------------------------


def test_plain_text_escaped_and_line_breaks_kept(club, login, game_master, player, owned, item):
    set_note(owned, item, "Watch it <script>now</script>\nsecond line", player)
    body = login(game_master).get(sheet_url(club, owned)).content.decode()
    assert "&lt;script&gt;" in body
    assert "<br>" in body
    assert "<script>" not in body


# --- one per character and item -------------------------------------------


def test_second_save_updates_same_row(club, login, player, owned, item):
    c = login(player)
    c.post(note_url(club, owned, item), {"text": "First."})
    c.post(note_url(club, owned, item), {"text": "Second."})
    assert ItemNote.objects.filter(character=owned, item=item).count() == 1
    assert ItemNote.objects.get(character=owned, item=item).text == "Second."


def test_unique_constraint(owned, item):
    ItemNote.objects.create(character=owned, item=item, text="One")
    with pytest.raises(IntegrityError):
        ItemNote.objects.create(character=owned, item=item, text="Two")


def test_note_on_stack_is_one_row(club, login, player, owned, item):
    # `owned` has 5 units of the item
    set_note(owned, item, "Stack note.", player)
    assert ItemNote.objects.count() == 1


# --- ledger and catalogue untouched ---------------------------------------


def test_ledger_and_catalogue_untouched(club, login, player, owned, item):
    before_entries = LedgerEntry.objects.count()
    name = item.name
    c = login(player)
    c.post(note_url(club, owned, item), {"text": "Note."})
    assert LedgerEntry.objects.count() == before_entries
    item.refresh_from_db()
    assert item.name == name


# --- hide and return ------------------------------------------------------


def test_note_hides_and_returns(club, login, player, owned, item):
    set_note(owned, item, "Hidden for now.", player)
    record(owned, "adjustment", [Line(item=item, quantity=-5)])
    body = login(player).get(sheet_url(club, owned)).content.decode()
    assert "Hidden for now." not in body
    assert ItemNote.objects.filter(character=owned, item=item).count() == 1
    assert login(player).get(note_url(club, owned, item)).status_code == 404
    record(owned, "award", [Line(item=item, quantity=3)])
    body = login(player).get(sheet_url(club, owned)).content.decode()
    assert 'title="Hidden for now."' in body


def test_partial_stack_change_keeps_note(club, login, player, owned, item):
    set_note(owned, item, "Keep me.", player)
    record(owned, "adjustment", [Line(item=item, quantity=-2)])
    assert ItemNote.objects.get(character=owned, item=item).text == "Keep me."


# --- no JavaScript --------------------------------------------------------


def test_note_page_works_without_javascript(club, login, player, owned, item):
    c = login(player)
    r = c.get(note_url(club, owned, item))
    assert r.status_code == 200
    content = r.content.decode()
    assert "<html" in content
    assert 'method="post"' in content
    assert "<textarea" in content
    assert 'type="submit"' in content
    assert "Save" in content
    assert "Cancel" in content
    r = c.post(note_url(club, owned, item), {"text": "No JS note."})
    assert r.status_code == 302
    assert r["Location"] == sheet_url(club, owned)


def test_htmx_get_returns_modal_fragment(club, login, player, owned, item):
    c = login(player)
    r = c.get(note_url(club, owned, item), HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    content = r.content.decode()
    assert "modal-header" in content
    assert "<html" not in content
