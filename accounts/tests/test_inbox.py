import re

import pytest
from django.urls import reverse

from accounts.models import Membership, Message
from ledger.models import LedgerEntry
from player_characters.models import Character
from starting_equipment.models import StartingEquipmentRequest


def _textarea_body(page):
    match = re.search(r'<textarea[^>]*name="body"[^>]*>(.*?)</textarea>', page, re.DOTALL)
    return match.group(1).strip("\n") if match else ""


SR = Message.Kind.STARTING_REQUEST


def _mem(user, club):
    return Membership.objects.get(user=user, club=club)


def _urls(club):
    return (
        reverse("accounts:message_new", args=[club.slug]),
        reverse("accounts:message_inbox", args=[club.slug]),
    )


def _inbox(club):
    return reverse("accounts:message_inbox", args=[club.slug])


def _status_url(club, pk):
    return reverse("accounts:message_status", args=[club.slug, pk])


def _bulk_url(club):
    return reverse("accounts:message_bulk_status", args=[club.slug])


@pytest.fixture
def msg(club, player):
    return Message.objects.create(club=club, sender=_mem(player, club), body="Missing ring")


@pytest.mark.story("U13")
def test_send_without_character(club, player, login):
    new, _ = _urls(club)
    r = login(player).post(new, {"body": "Hello admins"})
    assert r.status_code == 200
    assert "You have no character in this club." in r.content.decode()
    assert Message.objects.count() == 0


@pytest.mark.story("U13")
def test_send_with_own_character_and_list_shows_status(club, player, character, login):
    new, _ = _urls(club)
    c = login(player)
    c.post(new, {"body": "Lost a sword", "character": character.pk})
    assert Message.objects.get().character == character
    page = c.get(new).content.decode()
    assert "Lost a sword" in page and "Open" in page and "Aria" in page


@pytest.mark.story("U13")
def test_foreign_character_ignored(
    club, other_club, player, other_player, character, login, club_b_member
):
    owner = _mem(other_player, club)
    theirs = Character.objects.create(club=club, owner=owner, name="Theirs")
    b_char = Character.objects.create(
        club=other_club, owner=_mem(club_b_member, other_club), name="BChar"
    )
    new, _ = _urls(club)
    c = login(player)
    for ch in (theirs, b_char):
        assert c.post(new, {"body": "x", "character": ch.pk}).status_code == 302
    assert {m.character for m in Message.objects.all()} == {character}


@pytest.mark.story("U13")
def test_body_too_long_rejected(club, player, login):
    new, _ = _urls(club)
    r = login(player).post(new, {"body": "x" * 2001})
    assert r.status_code == 200 and Message.objects.count() == 0


@pytest.mark.story("U13")
def test_admin_handles_and_closes(club, club_admin, msg, login):
    _, inbox = _urls(club)
    c = login(club_admin)
    assert "Missing ring" in c.get(inbox).content.decode()
    r = c.post(_status_url(club, msg.pk), {"status": "handled", "filter": "open"})
    assert r.status_code == 302
    msg.refresh_from_db()
    assert msg.status == "handled"
    assert "Missing ring" not in c.get(inbox).content.decode()
    c.post(_status_url(club, msg.pk), {"status": "closed"})
    msg.refresh_from_db()
    assert msg.status == "closed"
    assert "Missing ring" in c.get(inbox + "?status=closed").content.decode()
    assert "Missing ring" not in c.get(inbox).content.decode()


@pytest.mark.story("U13")
def test_invalid_status_is_400_and_get_is_405(club, club_admin, msg, login):
    c = login(club_admin)
    assert c.post(_status_url(club, msg.pk), {"status": "bogus"}).status_code == 400
    assert c.get(_status_url(club, msg.pk)).status_code == 405


@pytest.mark.story("U13")
def test_player_forbidden(club, player, msg, login):
    _, inbox = _urls(club)
    c = login(player)
    assert c.get(inbox).status_code == 403
    assert c.post(_status_url(club, msg.pk), {"status": "closed"}).status_code == 403
    msg.refresh_from_db()
    assert msg.status == "open"


@pytest.mark.story("U13")
def test_site_admin_without_membership_cannot_send(club, site_admin, login):
    new, _ = _urls(club)
    c = login(site_admin)
    assert c.get(new).status_code == 200
    assert c.post(new, {"body": "hi"}).status_code == 403


@pytest.mark.story("U17")
def test_inbox_shows_sender_email_to_admins(club, club_admin, site_admin, player, msg, login):
    _, inbox = _urls(club)
    for u in (club_admin, site_admin):
        assert player.email in login(u).get(inbox).content.decode()


@pytest.mark.story("U12")
def test_club_b_member_gets_404(club, club_b_member, login):
    c = login(club_b_member)
    for url in _urls(club):
        assert c.get(url).status_code == 404


@pytest.mark.story("U12")
def test_club_b_message_not_in_club_a_inbox(club, other_club, site_admin, club_b_member, login):
    Message.objects.create(club=other_club, sender=_mem(club_b_member, other_club), body="SecretB")
    _, inbox = _urls(club)
    c = login(site_admin)
    assert "SecretB" not in c.get(inbox).content.decode()
    assert "SecretB" not in c.get(inbox + "?status=all").content.decode()


@pytest.mark.story("U12")
def test_status_post_cross_club_404(club, other_club, club_admin, club_b_member, login):
    m = Message.objects.create(club=other_club, sender=_mem(club_b_member, other_club), body="B")
    r = login(club_admin).post(_status_url(club, m.pk), {"status": "closed"})
    assert r.status_code == 404
    m.refresh_from_db()
    assert m.status == "open"


@pytest.mark.story("U30")
def test_bulk_mark_handled(club, club_admin, player, login):
    a = Message.objects.create(club=club, sender=_mem(player, club), body="one")
    b = Message.objects.create(club=club, sender=_mem(player, club), body="two")
    c = Message.objects.create(club=club, sender=_mem(player, club), body="three")
    _, inbox = _urls(club)
    cl = login(club_admin)
    r = cl.post(_bulk_url(club), {"message_ids": [a.pk, b.pk], "status": "handled"})
    assert r.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == "handled"
    assert b.status == "handled"
    assert c.status == "open"


@pytest.mark.story("U30")
def test_bulk_close(club, club_admin, player, login):
    a = Message.objects.create(club=club, sender=_mem(player, club), body="one")
    b = Message.objects.create(club=club, sender=_mem(player, club), body="two")
    cl = login(club_admin)
    r = cl.post(_bulk_url(club), {"message_ids": [a.pk, b.pk], "status": "closed"})
    assert r.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.status == "closed"
    assert b.status == "closed"


@pytest.mark.story("U30")
def test_bulk_reopen(club, club_admin, player, login):
    a = Message.objects.create(club=club, sender=_mem(player, club), body="one", status="closed")
    b = Message.objects.create(club=club, sender=_mem(player, club), body="two", status="closed")
    cl = login(club_admin)
    r = cl.post(_bulk_url(club), {"message_ids": [a.pk, b.pk], "status": "open"})
    assert r.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.status == "open"
    assert b.status == "open"


@pytest.mark.story("U30")
def test_bulk_empty_selection_warns(club, club_admin, player, login):
    cl = login(club_admin)
    # HTMX: 200 with a warning toast header; nothing is marked.
    r = cl.post(
        _bulk_url(club),
        {"status": "handled"},
        HTTP_HX_Request="true",
    )
    assert r.status_code == 200
    assert "Tick at least one message" in r["HX-Trigger"]
    # non-HTMX: 302 with a warning flash on the inbox page.
    r = cl.post(_bulk_url(club), {"status": "handled"})
    assert r.status_code == 302
    r = cl.get(r.url)
    assert "Tick at least one message" in r.content.decode()


@pytest.mark.story("U30")
def test_bulk_unknown_status_400(club, club_admin, player, login):
    m = Message.objects.create(club=club, sender=_mem(player, club), body="one")
    cl = login(club_admin)
    r = cl.post(_bulk_url(club), {"message_ids": [m.pk], "status": "bogus"})
    assert r.status_code == 400
    m.refresh_from_db()
    assert m.status == "open"


@pytest.mark.story("U30")
def test_bulk_non_admin_forbidden(club, club_admin, player, game_master, login):
    m = Message.objects.create(club=club, sender=_mem(player, club), body="one")
    cl = login(player)
    assert cl.post(_bulk_url(club), {"message_ids": [m.pk], "status": "handled"}).status_code == 403
    cl = login(game_master)
    assert cl.post(_bulk_url(club), {"message_ids": [m.pk], "status": "handled"}).status_code == 403
    m.refresh_from_db()
    assert m.status == "open"


@pytest.mark.story("U76")
def test_starting_request_kind_filter(club, club_admin, player, character, login):
    Message.objects.create(
        club=club,
        sender=_mem(player, club),
        kind=SR,
        body="Request magic starting item",
        character=character,
    )
    Message.objects.create(club=club, sender=_mem(player, club), body="Missing ring")
    c = login(club_admin)
    html = c.get(_inbox(club)).content.decode()
    assert "Request magic starting item" in html
    assert "Missing ring" in html
    html = c.get(_inbox(club) + "?kind=starting_request").content.decode()
    assert "Request magic starting item" in html and "Missing ring" not in html
    html = c.get(_inbox(club) + "?kind=message").content.decode()
    assert "Request magic starting item" not in html and "Missing ring" in html
    Message.objects.filter(kind=SR).update(status="closed")
    html = c.get(_inbox(club) + "?kind=starting_request&status=open").content.decode()
    assert "Request magic starting item" not in html


def _starting_request(club, character, item, sender):
    req = StartingEquipmentRequest.objects.create(
        club=club,
        character=character,
        item=item,
        quantity=1,
        status=StartingEquipmentRequest.Status.PENDING,
    )
    msg = Message.objects.create(
        club=club,
        sender=sender,
        character=character,
        body=f"{character.name} requests {item.name} as starting equipment.",
        kind=SR,
        status=Message.Status.OPEN,
    )
    req.message = msg
    req.save(update_fields=["message"])
    return req, msg


def _confirm_url(club, pk, decision):
    return reverse(
        "starting_equipment:request_decide_confirm",
        kwargs={"club_slug": club.slug, "pk": pk, "decision": decision},
    )


def _decide_urls(club, pk):
    approve = reverse(
        "starting_equipment:request_decide",
        kwargs={"club_slug": club.slug, "pk": pk, "decision": "approve"},
    )
    decline = reverse(
        "starting_equipment:request_decide",
        kwargs={"club_slug": club.slug, "pk": pk, "decision": "decline"},
    )
    return approve, decline


@pytest.mark.story("U30")
def test_starting_request_shows_grant_decline_buttons(
    club, club_admin, game_master, player, character, item, login
):
    """Admin and GM see Grant/Decline buttons on starting-request messages."""
    sender = _mem(player, club)
    req, _ = _starting_request(club, character, item, sender)
    inbox = _inbox(club) + "?kind=starting_request"

    for user in (club_admin, game_master):
        c = login(user)
        html = c.get(inbox).content.decode()
        assert _confirm_url(club, req.pk, "approve") in html
        assert _confirm_url(club, req.pk, "decline") in html


@pytest.mark.story("U30")
def test_starting_request_buttons_hidden_from_regular_member(club, player, character, item, login):
    """Regular members cannot see the inbox or the decision buttons."""
    sender = _mem(player, club)
    _starting_request(club, character, item, sender)
    c = login(player)
    assert c.get(_inbox(club) + "?kind=starting_request").status_code == 403


@pytest.mark.story("U30")
def test_starting_request_grant_approves_and_marks_message_handled(
    club, club_admin, player, character, item, login
):
    """Grant via inbox approves the request, grants the item, marks HANDLED."""
    sender = _mem(player, club)
    req, msg = _starting_request(club, character, item, sender)
    approve, _decline = _decide_urls(club, req.pk)

    c = login(club_admin)
    assert c.get(_confirm_url(club, req.pk, "approve"), HTTP_HX_REQUEST="true").status_code == 200

    response = c.post(approve, HTTP_HX_REQUEST="true")
    assert response.status_code == 204

    req.refresh_from_db()
    assert req.status == StartingEquipmentRequest.Status.APPROVED
    assert req.decided_by == club_admin

    msg.refresh_from_db()
    assert msg.status == Message.Status.HANDLED

    entry = LedgerEntry.objects.get(character=character, kind=LedgerEntry.Kind.AWARD)
    assert entry.note == f"Starting equipment: {item.name}"
    item_lines = [ln for ln in entry.lines.all() if ln.item is not None]
    assert len(item_lines) == 1
    assert item_lines[0].item == item
    assert item_lines[0].quantity == 1


@pytest.mark.story("U30")
def test_starting_request_decline_sets_declined_and_marks_message_handled(
    club, club_admin, player, character, item, login
):
    """Decline via inbox sets DECLINED + decision_note and marks the message HANDLED."""
    sender = _mem(player, club)
    req, msg = _starting_request(club, character, item, sender)
    _approve, decline = _decide_urls(club, req.pk)

    c = login(club_admin)
    assert c.get(_confirm_url(club, req.pk, "decline"), HTTP_HX_REQUEST="true").status_code == 200

    response = c.post(
        decline, {"decision_note": "Not appropriate for level 1"}, HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 204

    req.refresh_from_db()
    assert req.status == StartingEquipmentRequest.Status.DECLINED
    assert req.decision_note == "Not appropriate for level 1"

    msg.refresh_from_db()
    assert msg.status == Message.Status.HANDLED

    assert not LedgerEntry.objects.filter(character=character, kind=LedgerEntry.Kind.AWARD).exists()


@pytest.mark.story("U60")
@pytest.mark.parametrize(
    "template_key,expected",
    [
        ("loot", "I think Aria is missing: [items/coins] from the last session. Details: "),
        ("map", "Please mark Aria as having visited/found: [location/tile]. Details: "),
        ("shop", "Could [shop] start carrying [item]? Details: "),
        ("other", ""),
    ],
)
def test_message_template_prefills_body(club, player, character, login, template_key, expected):
    """GET ?template= pre-fills the message body with {character} substituted."""
    url = reverse("accounts:message_new", args=[club.slug])
    page = login(player).get(url + "?template=" + template_key).content.decode()
    assert _textarea_body(page) == expected


@pytest.mark.story("U60")
def test_message_template_invalid_param_leaves_body_empty(club, player, character, login):
    """An unknown ?template= value does not pre-fill the body."""
    url = reverse("accounts:message_new", args=[club.slug])
    page = login(player).get(url + "?template=bogus").content.decode()
    assert _textarea_body(page) == ""


@pytest.mark.story("U60")
def test_message_template_submitted_body_is_saved(club, player, character, login):
    """Submitting a template-prefilled form saves the filled body."""
    url = reverse("accounts:message_new", args=[club.slug])
    c = login(player)
    body = "I think Aria is missing: [items/coins] from the last session. Details: lost ring"
    c.post(url + "?template=loot", {"body": body})
    assert Message.objects.get().body == body


@pytest.mark.story("U60")
def test_message_form_has_no_template_field():
    from accounts.forms.inbox import MessageForm

    form = MessageForm()
    assert "template" not in form.fields
    assert "template" not in form.Meta.fields


@pytest.mark.story("U30")
def test_inbox_select_all_apply_and_row_labels(club, club_admin, player, login):
    """Select all is CSP-safe, Apply is readable, row checkboxes are labelled, columns respond."""
    Message.objects.create(club=club, sender=_mem(player, club), body="One ring")
    Message.objects.create(club=club, sender=_mem(player, club), body="Two rings")
    _, inbox = _urls(club)
    page = login(club_admin).get(inbox).content.decode()

    # No inline event handlers: select-all must not use onclick (CSP script-src 'self').
    assert "onclick" not in page

    # Select-all control lives in the bulk form, outside the swapped #inbox-list.
    assert "data-wm-check-all" in page
    assert 'data-wm-check-all-for="message_ids"' in page
    bar_start = page.index('<div id="inbox-bulk-bar"')
    bar = page[bar_start : page.index("</div>", bar_start)]
    assert "data-wm-check-all" in bar
    assert 'id="inbox-list"' not in bar

    # Apply button uses the readable outline variant, not the solid secondary.
    assert 'class="btn btn-sm btn-outline-secondary"' in bar
    assert 'class="btn btn-sm btn-secondary"' not in bar

    # Every row checkbox has a unique accessible name.
    labels = re.findall(r'aria-label="Select message from [^"]+"', page)
    assert len(labels) == 2
    assert len(set(labels)) == 2

    # Responsive utilities: message text in the From cell below 576px, other columns hide.
    assert "d-sm-none" in page
    assert "d-none d-sm-table-cell" in page

    # Select-all stays on one line.
    assert 'class="form-check-label text-nowrap"' in page


@pytest.mark.story("U13")
def test_inbox_phone_block_hides_email_shows_status(club, club_admin, player, msg, login):
    """Below 576px the email is hidden, the status is in the phone block."""
    _, inbox = _urls(club)
    page = login(club_admin).get(inbox).content.decode()
    assert 'class="wm-muted-line d-none d-sm-block"' in page
    assert "wm-req-summary" not in page
    assert "status_badge" not in page
    # The phone block shows the sender, body and status.
    assert "Missing ring" in page
    assert "Open" in page


@pytest.mark.story("U13")
def test_inbox_starting_request_shows_badge_in_phone_block(
    club, club_admin, player, character, login
):
    """A starting-request message shows its badge in the phone block."""
    sender = _mem(player, club)
    Message.objects.create(
        club=club,
        sender=sender,
        kind=SR,
        body="Request magic starting item",
        character=character,
    )
    _, inbox = _urls(club)
    page = login(club_admin).get(inbox).content.decode()
    assert 'class="badge text-bg-primary">Starting request</span>' in page


def test_wm_check_sm_is_phone_scoped_in_css():
    """The checkbox size rule sits inside the phone media query, so wider layouts are unchanged."""
    import re
    from pathlib import Path

    css = Path("static/css/areas/accounts.css").read_text()
    for m in re.finditer(r"[^{}]*\.wm-check-sm[^{}]*\{", css):
        before = css[: m.start()]
        last_media = before.rfind("@media")
        assert last_media != -1
        assert "max-width: 575.98px" in before[last_media:]
        assert before[last_media:].count("{") - before[last_media:].count("}") >= 1
