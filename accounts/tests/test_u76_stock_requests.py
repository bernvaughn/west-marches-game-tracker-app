import pytest
from django.core.management import call_command
from django.urls import reverse

from accounts import approvals
from accounts.models import Membership, Message
from player_characters.models import Character

pytestmark = [pytest.mark.django_db, pytest.mark.story("U76")]

SR = Message.Kind.STOCK_REQUEST


def _mem(user, club):
    return Membership.objects.get(user=user, club=club)


def _new(club):
    return reverse("accounts:stock_request_new", args=[club.slug])


def _inbox(club):
    return reverse("accounts:message_inbox", args=[club.slug])


def _both(club, player, character):
    sr = Message.objects.create(
        club=club, sender=_mem(player, club), character=character, kind=SR, body="Want plate armour"
    )
    m = Message.objects.create(club=club, sender=_mem(player, club), body="Missing ring")
    return sr, m


def test_send_as_selected_character(club, player, character, login):
    other = Character.objects.create(club=club, owner=_mem(player, club), name="Zed")
    c = login(player)
    r = c.post(_new(club), {"body": "Armor please", "character": other.pk})
    assert r.status_code == 302
    msg = Message.objects.get()
    assert msg.kind == SR
    assert msg.sender == _mem(player, club)
    assert msg.character in (character, other)
    assert "Armor please" in c.get(_new(club)).content.decode()


def test_no_character_shows_empty_state(club, other_player, login):
    r = login(other_player).post(_new(club), {"body": "x"})
    assert r.status_code == 200
    assert "You have no character in this club." in r.content.decode()
    assert Message.objects.count() == 0


def test_non_member_lock_and_post_403(club, site_admin, other_club, club_b_member, login):
    r = login(site_admin).get(_new(club))
    assert "Only club members" in r.content.decode()
    assert login(site_admin).post(_new(club), {"body": "x"}).status_code == 403


def test_nav_entry(club, player, login):
    html = login(player).get(reverse("club_home", args=[club.slug])).content.decode()
    assert "Request stock" in html


def test_badge_and_filter(club, club_admin, player, character, login):
    _both(club, player, character)
    c = login(club_admin)
    html = c.get(_inbox(club)).content.decode()
    assert "Want plate armour" in html and "Missing ring" in html
    assert html.count("Stock request</span>") == 1
    html = c.get(_inbox(club) + "?kind=stock_request").content.decode()
    assert "Want plate armour" in html and "Missing ring" not in html
    html = c.get(_inbox(club) + "?kind=message").content.decode()
    assert "Want plate armour" not in html and "Missing ring" in html
    html = c.get(_inbox(club) + "?kind=bogus").content.decode()
    assert "Want plate armour" in html and "Missing ring" in html
    Message.objects.filter(kind=SR).update(status="closed")
    html = c.get(_inbox(club) + "?kind=stock_request&status=open").content.decode()
    assert "Want plate armour" not in html


def test_no_give_for_stock_requests(club, club_admin, player, character, login):
    sr, m = _both(club, player, character)
    c = login(club_admin)
    html = c.get(_inbox(club)).content.decode()
    assert html.count('aria-label="Give coins"') == 1
    for kind in ("coins", "items", "map"):
        url = reverse(f"accounts:message_give_{kind}", args=[club.slug, sr.pk])
        assert c.get(url).status_code == 404
        assert c.post(url, {}).status_code == 404
        ok = reverse(f"accounts:message_give_{kind}", args=[club.slug, m.pk])
        assert c.get(ok).status_code == 200


def test_status_actions_keep_kind(club, club_admin, player, character, login):
    sr, _ = _both(club, player, character)
    c = login(club_admin)
    confirm = reverse("accounts:message_status_confirm", args=[club.slug, sr.pk, "handled"])
    assert c.get(confirm + "?kind=stock_request").status_code == 200
    url = reverse("accounts:message_status", args=[club.slug, sr.pk])
    for status in ("handled", "closed", "open"):
        r = c.post(url, {"status": status, "filter": "all", "kind": "stock_request"})
        assert r.status_code == 302
        assert r["Location"].endswith("?status=all&kind=stock_request")
        sr.refresh_from_db()
        assert sr.status == status


def test_inbox_admin_only(club, player, character, login):
    _both(club, player, character)
    assert login(player).get(_inbox(club)).status_code == 403


def test_cross_club_isolation(club, other_club, club_admin, club_b_member, login):
    sr = Message.objects.create(
        club=other_club, sender=_mem(club_b_member, other_club), kind=SR, body="SecretStockB"
    )
    c = login(club_admin)
    for q in ("", "?kind=stock_request", "?kind=all&status=all"):
        assert "SecretStockB" not in c.get(_inbox(club) + q).content.decode()
    url = reverse("accounts:message_status", args=[club.slug, sr.pk])
    assert c.post(url, {"status": "closed"}).status_code == 404
    assert login(club_b_member).get(_inbox(club)).status_code == 404


def test_counts_in_approvals(rf, club, club_admin, player, character):
    def count():
        request = rf.get("/")
        request.user = club_admin
        request.club = club
        request.membership = _mem(club_admin, club)
        return {a.label: a.count for a in approvals.pending_approvals(request)}.get("Messages", 0)

    before = count()
    sr = Message.objects.create(club=club, sender=_mem(player, club), kind=SR, body="x")
    assert count() == before + 1
    sr.status = "handled"
    sr.save()
    assert count() == before


def test_seed_demo_idempotent():
    call_command("seed_demo")
    call_command("seed_demo")
    qs = Message.objects.filter(kind=SR)
    assert qs.count() == 1
    assert qs.get().sender.user.email == "alice@example.com"
