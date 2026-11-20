import pytest
from django.urls import reverse
from ledger.services import Line, record
from player_characters.junk import set_junk

pytestmark = [pytest.mark.django_db, pytest.mark.story("U129")]

def test_debug(club, login, player, character, shop, parchment):
    record(character, "award", [Line(item=parchment, quantity=10)])
    set_junk(character, parchment, 2, player)
    c = login(player)
    url = reverse("shops:sell_item", args=[club.slug, shop.pk, parchment.pk])
    r = c.post(url, {"character": character.id, "quantity": 5}, HTTP_HX_REQUEST="true")
    with open("/tmp/debug_body.txt", "w") as f:
        f.write(f"STATUS: {r.status_code}\n")
        f.write(f"BODY: {r.content.decode()}\n")
