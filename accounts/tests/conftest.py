import pytest

from accounts.models import Membership, User


def _member(club, email, name, **flags):
    user = User.objects.create_user(email, password="pw", display_name=name)
    Membership.objects.create(user=user, club=club, **flags)
    return user


@pytest.fixture
def club_b_member(other_club):
    return _member(other_club, "bmember@example.com", "B Member")


@pytest.fixture
def club_b_admin(other_club):
    return _member(other_club, "badmin@example.com", "B Admin", is_club_admin=True)
