"""Browser guard: no page may log a console error. Run with `pytest -m browser`."""

import pytest


@pytest.mark.browser
def test_no_console_errors_on_any_page():
    from scripts.console_sweep import sweep

    problems = sweep()
    assert not problems, "\n".join(problems)
