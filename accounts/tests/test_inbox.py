import pytest
from django.urls import reverse

from accounts.models import Membership, Message
from player_characters.models import Character

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
def test_bulk_empty_selection_400(club, club_admin, player, login):
    cl = login(club_admin)
    assert cl.post(_bulk_url(club), {"status": "handled"}).status_code == 400


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
