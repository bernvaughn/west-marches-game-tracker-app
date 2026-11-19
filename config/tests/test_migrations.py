"""The test settings switch migrations off for speed, so nothing else runs them.

This test turns them back on and builds the migration graph. A bad dependency, such as the
literal string "AUTH_USER_MODEL" instead of `settings.AUTH_USER_MODEL`, or two leaf
migrations in one app, then fails here instead of on someone's first `manage.py migrate`.
"""

from django.db.migrations.loader import MigrationLoader
from django.test import override_settings


@override_settings(MIGRATION_MODULES={})
def test_migration_graph_builds():
    # `None` = do not read the database. Raises ValueError on a dependency on an unknown app.
    MigrationLoader(None)


@override_settings(MIGRATION_MODULES={})
def test_no_app_has_conflicting_migrations():
    assert MigrationLoader(None).detect_conflicts() == {}
