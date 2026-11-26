"""Grep test: ensure SessionRSVP does not appear in the codebase.

This test fails if any Python file (excluding migrations and this test file)
contains the string "SessionRSVP". This ensures the old model has been fully
removed from the code.
"""

import os
import subprocess

import pytest


def test_no_sessionrsvp_in_codebase():
    """Search for SessionRSVP in all .py files except migrations and this test."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Use grep to find SessionRSVP in .py files
    result = subprocess.run(
        ["grep", "-r", "SessionRSVP", "--include=*.py", root],
        capture_output=True,
        text=True,
    )

    # Filter out allowed occurrences:
    # - migrations/ (historical migrations reference the old model)
    # - this test file itself
    # - test_rsvp_merge.py (was deleted)
    # - play_sessions/models.py (the merge_rsvps_to_player function references
    #   SessionRSVP for the historical migration 0004; this is expected)
    allowed_patterns = [
        "migrations/",
        "test_no_sessionrsvp.py",
        "play_sessions/models.py",
    ]

    violations = []
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if line and not any(pattern in line for pattern in allowed_patterns):
                violations.append(line)

    if violations:
        pytest.fail(
            "Found SessionRSVP references in codebase (excluding migrations):\n"
            + "\n".join(violations)
        )


def test_no_sessionrsvp_imports():
    """Specifically check for import statements containing SessionRSVP."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    result = subprocess.run(
        ["grep", "-r", "from.*import.*SessionRSVP", "--include=*.py", root],
        capture_output=True,
        text=True,
    )

    violations = []
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if line and "migrations/" not in line and "test_no_sessionrsvp.py" not in line:
                violations.append(line)

    result2 = subprocess.run(
        ["grep", "-r", "import.*SessionRSVP", "--include=*.py", root],
        capture_output=True,
        text=True,
    )

    if result2.stdout:
        for line in result2.stdout.strip().split("\n"):
            if line and "migrations/" not in line and "test_no_sessionrsvp.py" not in line:
                violations.append(line)

    if violations:
        pytest.fail(
            "Found SessionRSVP imports in codebase (excluding migrations):\n"
            + "\n".join(violations)
        )
