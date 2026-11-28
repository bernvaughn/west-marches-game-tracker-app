"""Browser-free tests for the pure helpers in scripts/flow_checks/flow_10_admin_message.py."""

from scripts.flow_checks.flow_10_admin_message import (
    coins_to_cp,
    detail_pk,
    message_pk,
    rows_matching,
    status_of_badge,
)


def test_message_pk_reads_the_tickbox_value():
    row = '<td><input type="checkbox" name="message_ids" value="14" class="x"></td>'
    assert message_pk(row) == 14
    assert message_pk('<input name="message_ids"\n value="7">') == 7
    assert message_pk("<td>no tick-box here</td>") is None
    assert message_pk("") is None
    assert message_pk(None) is None


def test_detail_pk_reads_the_path():
    assert detail_pk("/c/demo/accounts/messages/12/") == 12
    assert detail_pk("/c/demo/accounts/messages/") is None
    assert detail_pk("/c/demo/accounts/messages/new/") is None
    assert detail_pk("/c/demo/accounts/messages/12/status/") is None
    assert detail_pk("") is None


def test_rows_matching_filters_by_needle():
    texts = ["Open | Flow 10 message", "Handled | Other message", "Open | Flow 10 follow-up"]
    assert rows_matching(texts, "Flow 10") == [
        "Open | Flow 10 message",
        "Open | Flow 10 follow-up",
    ]
    assert rows_matching(texts, "Other") == ["Handled | Other message"]
    assert rows_matching(texts, "Closed") == []


def test_status_of_badge_normalises():
    assert status_of_badge("Open") == "open"
    assert status_of_badge("  Handled\n") == "handled"
    assert status_of_badge("Closed") == "closed"
    assert status_of_badge("") == ""
    assert status_of_badge(None) == ""


def test_coins_to_cp_sums_every_coin_part():
    assert coins_to_cp("1 gp") == 100
    assert coins_to_cp("12 gp 3 sp 4 cp") == 1234
    assert coins_to_cp("1,250 gp") == 125_000
    assert coins_to_cp("2 pp") == 2000
    assert coins_to_cp("Items & Coins Granted Aria 1 gp") == 100
    assert coins_to_cp("no coins") is None
    assert coins_to_cp("") is None
    assert coins_to_cp(None) is None
