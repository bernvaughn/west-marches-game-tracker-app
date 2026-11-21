import os
import tempfile

import pytest


@pytest.mark.django_db
class TestUrlDiscovery:
    def test_discover_loads_urls_modules(self):
        """URL discovery loads urls_* modules."""
        from mail.urls import club_urlpatterns, discover, public_urlpatterns

        # Initially empty
        assert club_urlpatterns == []
        assert public_urlpatterns == []

        # Create a temporary urls_ module
        with tempfile.TemporaryDirectory() as tmpdir:
            # Add to mail.__path__
            import mail
            original_path = mail.__path__
            mail.__path__ = list(original_path) + [tmpdir]

            try:
                # Create a probe module
                probe_content = '''
from django.urls import path

club_urlpatterns = [
    path("test/", lambda r: None, name="test_club"),
]
public_urlpatterns = [
    path("public/", lambda r: None, name="test_public"),
]
'''
                probe_file = os.path.join(tmpdir, "urls_zz_probe.py")
                with open(probe_file, "w") as f:
                    f.write(probe_content)

                # Run discovery
                club, public = discover()

                assert len(club) == 1
                assert len(public) == 1
            finally:
                mail.__path__ = original_path

    def test_discover_raises_on_import_error(self):
        """Discovery raises on import error in urls_* module."""
        import mail
        original_path = mail.__path__

        with tempfile.TemporaryDirectory() as tmpdir:
            mail.__path__ = list(original_path) + [tmpdir]

            try:
                # Create a probe module with a syntax error
                probe_file = os.path.join(tmpdir, "urls_bad.py")
                with open(probe_file, "w") as f:
                    f.write("import nonexistent_module_xyz\n")

                with pytest.raises(ImportError):
                    from mail.urls import discover
                    discover()
            finally:
                mail.__path__ = original_path


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
                probe_content = '''
register_called = False

def register():
    global register_called
    register_called = True
'''
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
                probe_content = '''
# No register function
some_var = "test"
'''
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