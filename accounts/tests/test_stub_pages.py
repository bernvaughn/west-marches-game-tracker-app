import pytest
from django.urls import reverse

from accounts.tests.test_scoping import ROUTES

pytestmark = pytest.mark.story("FOUNDATION")


@pytest.mark.parametrize("route", ROUTES)
def test_index_ok_for_member(route, login, player, club):
    client = login(player)
    if route == "club_home":
        # Players are redirected to dashboard
        response = client.get(reverse(route, args=[club.slug]), follow=True)
        assert response.status_code == 200
        # Check redirect chain
        assert any("/accounts/dashboard/" in url for url, _ in response.redirect_chain)
    else:
        assert client.get(reverse(route, args=[club.slug])).status_code == 200
