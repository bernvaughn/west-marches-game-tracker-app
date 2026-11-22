import importlib
import os
import sys
import tempfile

import pytest

PROBE_URLS = """
from django.http import HttpResponse
from django.urls import path


def _view(request, **kwargs):
    return HttpResponse("ok")


club_urlpatterns = [path("zz-club/", _view, name="zz_club")]
public_urlpatterns = [path("zz-public/", _view, name="zz_public")]
"""


def _reload_urlconf():
    """Re-run discovery at import and rebuild the root URLconf."""
    from django.urls import clear_url_caches

    import config.urls
    import mail.urls

    importlib.reload(mail.urls)
    importlib.reload(config.urls)
    clear_url_caches()


@pytest.fixture
def probe_urls_module(tmp_path):
    """Put a ``urls_zz_probe`` module on ``mail.__path__`` for one test."""
    import mail

    (tmp_path / "urls_zz_probe.py").write_text(PROBE_URLS)
    original_path = mail.__path__
    mail.__path__ = list(original_path) + [str(tmp_path)]
    try:
        yield
    finally:
        mail.__path__ = original_path
        sys.modules.pop("mail.urls_zz_probe", None)
        _reload_urlconf()


@pytest.mark.django_db
class TestUrlDiscovery:
    def test_discovered_urls_are_mounted(self, probe_urls_module):
        """A urls_* module is reachable through the real URLconf."""
        from django.urls import reverse

        _reload_urlconf()

        assert reverse("mail_public:zz_public") == "/mail/zz-public/"
        assert reverse("mail:zz_club", kwargs={"club_slug": "demo"}) == "/c/demo/mail/zz-club/"

    def test_discover_fills_the_same_lists_in_place(self, probe_urls_module):
        """discover() never rebinds, so include() sees the patterns."""
        from mail import urls

        club_list, public_list = urls.club_urlpatterns, urls.public_urlpatterns

        club, public = urls.discover()

        assert club is club_list is urls.club_urls[0]
        assert public is public_list is urls.public_urls[0]
        # Probe URLs should be present (other urls_* modules may also be discovered)
        assert "zz_club" in [p.name for p in club]
        assert "zz_public" in [p.name for p in public]

        # Running it again does not duplicate patterns.
        urls.discover()
        assert "zz_club" in [p.name for p in club]
        assert "zz_public" in [p.name for p in public]

    def test_discover_raises_on_import_error(self, tmp_path):
        """Discovery raises on import error in urls_* module."""
        import mail
        from mail.urls import discover

        (tmp_path / "urls_bad.py").write_text("import nonexistent_module_xyz\n")
        original_path = mail.__path__
        mail.__path__ = list(original_path) + [str(tmp_path)]
        try:
            with pytest.raises(ImportError):
                discover()
        finally:
            mail.__path__ = original_path
            sys.modules.pop("mail.urls_bad", None)
            discover()


@pytest.mark.django_db
class TestHooksDiscovery:
    def test_hooks_discovery_loads_hooks_modules(self, monkeypatch):
        """Hooks discovery loads hooks_* modules and calls register()."""
        from mail.apps import discover as discover_hooks

        # Create a temporary hooks module
        with tempfile.TemporaryDirectory() as tmpdir:
            import mail

            original_path = mail.__path__
            mail.__path__ = list(original_path) + [tmpdir]

            try:
                probe_content = """
register_called = False

def register():
    global register_called
    register_called = True
"""
                probe_file = os.path.join(tmpdir, "hooks_zz_probe.py")
                with open(probe_file, "w") as f:
                    f.write(probe_content)

                # Discover and import hooks
                modules = discover_hooks("hooks_")

                # Find our probe module and call register
                for module in modules:
                    if hasattr(module, "register"):
                        module.register()
                    if hasattr(module, "register_called"):
                        assert module.register_called is True
            finally:
                mail.__path__ = original_path

    def test_hooks_discovery_skips_module_without_register(self, monkeypatch):
        """Hooks module without register() is imported but not an error."""
        from mail.apps import discover as discover_hooks

        with tempfile.TemporaryDirectory() as tmpdir:
            import mail

            original_path = mail.__path__
            mail.__path__ = list(original_path) + [tmpdir]

            try:
                probe_content = """
# No register function
some_var = "test"
"""
                probe_file = os.path.join(tmpdir, "hooks_no_register.py")
                with open(probe_file, "w") as f:
                    f.write(probe_content)

                modules = discover_hooks("hooks_")

                # Module should be imported
                found = False
                for module in modules:
                    if hasattr(module, "some_var"):
                        found = True
                        assert module.some_var == "test"
                assert found
            finally:
                mail.__path__ = original_path

    def test_hooks_discovery_raises_on_import_error(self, monkeypatch):
        """Hooks discovery raises on import error."""
        from mail.apps import discover as discover_hooks

        with tempfile.TemporaryDirectory() as tmpdir:
            import mail

            original_path = mail.__path__
            mail.__path__ = list(original_path) + [tmpdir]

            try:
                probe_file = os.path.join(tmpdir, "hooks_bad.py")
                with open(probe_file, "w") as f:
                    f.write("import nonexistent_module_xyz\n")

                with pytest.raises(ImportError):
                    discover_hooks("hooks_")
            finally:
                mail.__path__ = original_path


@pytest.mark.django_db
class TestPackagesExist:
    def test_views_package_exists(self):
        """mail.views package exists."""
        import mail.views

        assert hasattr(mail.views, "__path__")

    def test_management_package_exists(self):
        """mail.management package exists."""
        import mail.management

        assert hasattr(mail.management, "__path__")

    def test_management_commands_package_exists(self):
        """mail.management.commands package exists."""
        import mail.management.commands

        assert hasattr(mail.management.commands, "__path__")

    def test_extras_registry_works(self):
        """Extras registry can register and render extras."""
        from mail.builders import register_email_extra, render_extras

        def extra_fn(ctx):
            return "extra text", "extra html"

        register_email_extra("test_kind", extra_fn)
        text, html = render_extras("test_kind", {})
        assert text == "extra text"
        assert html == "extra html"

    def test_club_reply_to(self):
        """club_reply_to returns contact email or None."""
        from accounts.models import Club
        from mail.builders import club_reply_to
        from mail.models import ClubMailSettings

        club = Club.objects.create(name="Test", slug="test")
        assert club_reply_to(club) is None

        ClubMailSettings.objects.create(club=club, contact_email="contact@test.com")
        assert club_reply_to(club) == "contact@test.com"

        assert club_reply_to(None) is None

    def test_base_context(self):
        """base_context builds expected context."""

        from accounts.models import Club
        from mail.builders import base_context
        from mail.models import ClubMailSettings

        club = Club.objects.create(name="Test Club", slug="test")
        ctx = base_context(club, "welcome")
        assert ctx["club"] == club
        assert ctx["kind"] == "welcome"
        assert "site_url" in ctx
        assert len(ctx["footer_lines"]) >= 2
        assert "Test Club" in ctx["footer_lines"][0]

        # With contact email
        ClubMailSettings.objects.create(club=club, contact_email="contact@test.com")
        ctx = base_context(club, "welcome")
        assert any("contact@test.com" in line for line in ctx["footer_lines"])
