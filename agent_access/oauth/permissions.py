from oauth2_provider.dcr import enforce_csrf
from oauth2_provider.utils import parse_bearer_token

from accounts.models import Membership


class ClubAdminOrGameMasterDCRPermission:
    """
    Allow OAuth client registration only to authenticated users who are
    club admins or game masters in at least one club.
    """

    def has_permission(self, request) -> bool:
        # Must be authenticated
        if not (request.user and request.user.is_authenticated):
            return False

        # Bearer token requests bypass CSRF (browsers never send cross-site)
        if parse_bearer_token(request.META.get("HTTP_AUTHORIZATION", "")) is not None:
            # Check if user is club admin or GM
            return Membership.objects.filter(
                user=request.user,
                is_club_admin=True
            ).exists() or Membership.objects.filter(
                user=request.user,
                is_game_master=True
            ).exists()

        # Session-authenticated requests need CSRF protection
        if not enforce_csrf(request):
            return False

        # Check if user is club admin or GM
        return Membership.objects.filter(
            user=request.user,
            is_club_admin=True
        ).exists() or Membership.objects.filter(
            user=request.user,
            is_game_master=True
        ).exists()