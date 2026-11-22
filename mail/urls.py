"""URL discovery for the mail app.

Drop-in modules named ``mail/urls_*.py`` may define ``club_urlpatterns``
(mounted under ``c/<club_slug>/mail/``, namespace ``mail``) and
``public_urlpatterns`` (mounted under ``mail/``, namespace ``mail_public``).

There is ONE list object per set. ``discover()`` fills it in place and never
rebinds the names, so the lists inside ``club_urls`` and ``public_urls`` always
see the discovered patterns. Discovery runs once when this module is imported.
An import error in a ``urls_*`` module is raised, never swallowed.
"""

import pkgutil
from importlib import import_module

club_urlpatterns = []
public_urlpatterns = []

# Tuples for include(): (patterns, app_name). They hold the lists above.
club_urls = (club_urlpatterns, "mail")
public_urls = (public_urlpatterns, "mail_public")


def discover():
    """Rebuild both pattern lists, in place, from the ``urls_*`` modules."""
    import mail

    club_urlpatterns.clear()
    public_urlpatterns.clear()

    for module_info in sorted(pkgutil.iter_modules(mail.__path__), key=lambda m: m.name):
        if not module_info.name.startswith("urls_"):
            continue
        module = import_module(f"mail.{module_info.name}")
        club_urlpatterns.extend(getattr(module, "club_urlpatterns", []))
        public_urlpatterns.extend(getattr(module, "public_urlpatterns", []))

    return club_urlpatterns, public_urlpatterns


discover()
