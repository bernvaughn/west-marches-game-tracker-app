"""Guard against defects that pytest alone does not catch.

pytest does not run Django system checks or compare migrations to models.
These tests make CI fail when either is broken.
"""

from io import StringIO

import pytest
from django.core.management import call_command


def test_system_checks_pass():
    call_command("check", stdout=StringIO())


@pytest.mark.django_db
def test_no_missing_migrations():
    out = StringIO()
    call_command("makemigrations", "--check", "--dry-run", stdout=out)
    assert "No changes detected" in out.getvalue()
