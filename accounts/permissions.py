from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Membership


def _membership(user, club):
    if not user.is_authenticated or club is None:
        return None
    return Membership.objects.filter(user=user, club=club).first()


def is_club_admin(user, club):
    if user.is_superuser:
        return True
    m = _membership(user, club)
    return bool(m and m.is_club_admin)


def is_game_master(user, club):
    if user.is_superuser:
        return True
    m = _membership(user, club)
    return bool(m and m.is_game_master)


def can_view_inventory(user, character):
    """Owner, a GM or admin of the character's club, or a site admin."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    club = character.club
    m = _membership(user, club)
    if m is None:
        return False
    return character.owner_id == m.id or m.is_game_master or m.is_club_admin


def can_see_email(user, club):
    """Only club admins (and site admins) see member emails."""
    return is_club_admin(user, club)


def can_reset_password(actor, target):
    """Site admin always; a club admin only if they administer every club the target is in."""
    if not actor.is_authenticated:
        return False
    if actor.is_superuser:
        return True
    if target.is_superuser:
        return False
    target_clubs = set(Membership.objects.filter(user=target).values_list("club_id", flat=True))
    if not target_clubs:
        return False
    admin_clubs = set(
        Membership.objects.filter(user=actor, is_club_admin=True).values_list("club_id", flat=True)
    )
    return target_clubs <= admin_clubs


def _club_check(predicate):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            club = getattr(request, "club", None)
            if club is None or not predicate(request):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def _is_member(request):
    return request.user.is_superuser or request.membership is not None


club_member_required = _club_check(_is_member)
club_admin_required = _club_check(lambda r: is_club_admin(r.user, r.club))
game_master_required = _club_check(lambda r: is_game_master(r.user, r.club))
admin_or_gm_required = _club_check(
    lambda r: is_club_admin(r.user, r.club) or is_game_master(r.user, r.club)
)


def site_admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
