from django.contrib.auth.views import redirect_to_login
from django.http import Http404

from .models import Club, Membership


class ClubMiddleware:
    """Resolve /c/<club_slug>/ into request.club and request.membership."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.club = None
        request.membership = None
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        slug = view_kwargs.get("club_slug")
        if slug is None:
            return None
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        club = Club.objects.filter(slug=slug).first()
        if club is None:
            raise Http404("No such club")
        membership = Membership.objects.filter(user=request.user, club=club).first()
        if membership is None and not request.user.is_superuser:
            raise Http404("No such club")
        request.club = club
        request.membership = membership
        return None
