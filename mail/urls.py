"""URL discovery for mail app.

Scans for urls_* modules and builds club_urlpatterns and public_urlpatterns.
"""

import pkgutil
from importlib import import_module

club_urlpatterns = []
public_urlpatterns = []


def discover():
    """Discover all urls_* modules and build the pattern lists."""
    global club_urlpatterns, public_urlpatterns
    club_urlpatterns = []
    public_urlpatterns = []

    import mail
    for module_info in pkgutil.iter_modules(mail.__path__):
        if module_info.name.startswith("urls_"):
            module = import_module(f"mail.{module_info.name}")

            if hasattr(module, "club_urlpatterns"):
                club_urlpatterns.extend(module.club_urlpatterns)
            if hasattr(module, "public_urlpatterns"):
                public_urlpatterns.extend(module.public_urlpatterns)

    return club_urlpatterns, public_urlpatterns


# Export as tuples for include()
club_urls = (club_urlpatterns, "mail")
public_urls = (public_urlpatterns, "mail_public")