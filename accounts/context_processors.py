from .models import Club, SiteSettings


def clubs(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        user_clubs = []
    elif user.is_superuser:
        user_clubs = Club.objects.all()
    else:
        user_clubs = Club.objects.filter(memberships__user=user).distinct()
    return {
        "user_clubs": user_clubs,
        "club": getattr(request, "club", None),
        "donate_url": SiteSettings.load().donate_url,
    }
