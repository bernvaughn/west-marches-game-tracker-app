import pytest
from django.urls import reverse

from accounts.tests.test_scoping import ROUTES

pytestmark = pytest.mark.story("FOUNDATION")


@pytest.mark.parametrize("route", ROUTES)
def test_index_ok_for_member(route, login, player, club):
    assert login(player).get(reverse(route, args=[club.slug])).status_code == 200
