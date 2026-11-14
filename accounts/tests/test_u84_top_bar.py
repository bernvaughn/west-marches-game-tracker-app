import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_skip_link_and_main_id(client, django_user_model):
    user = django_user_model.objects.create_user(email="a@example.com", password="x")
    client.force_login(user)
    html = client.get(reverse("home")).content.decode()
    assert 'href="#main"' in html
    assert html.index('href="#main"') < html.index('<nav class="site-header')
    assert '<main id="main"' in html


def test_icon_only_buttons_have_tooltips(client, django_user_model):
    user = django_user_model.objects.create_user(email="b@example.com", password="x")
    client.force_login(user)
    html = client.get(reverse("home")).content.decode()
    assert 'title="Open menu" data-wm-tooltip' in html
    assert 'title="Close menu" data-wm-tooltip' in html
