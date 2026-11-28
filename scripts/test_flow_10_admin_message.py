"""Browser-free tests for the pure helpers in scripts/flow_checks/flow_10_admin_message.py."""

from scripts.flow_checks.flow_10_admin_message import first_int, rows_matching, status_of_badge


def test_first_int_reads_quantity():
    assert first_int("× 3") == 3
    assert first_int("25 sheet") == 25
    assert first_int("× 10") == 10
    assert first_int(None) is None
    assert first_int("none") is None


def test_rows_matching_filters_by_needle():
    texts = ["Open | Flow 10 message", "Handled | Other message", "Open | Flow 10 follow-up"]
    assert rows_matching(texts, "Flow 10") == [
        "Open | Flow 10 message",
        "Open | Flow 10 follow-up",
    ]
    assert rows_matching(texts, "Handled") == ["Handled | Other message"]
    assert rows_matching(texts, "Closed") == []


def test_status_of_badge_normalises():
    assert status_of_badge("Open") == "open"
    assert status_of_badge("Handled") == "handled"
    assert status_of_badge("Closed") == "closed"
    assert status_of_badge("  Open  ") == "open"
