"""Browser-free tests for the pure helpers in scripts/flow_checks/flow_3_quest.py."""

from scripts.flow_checks.flow_3_quest import first_int, parse_coins, wait_until


def test_parse_coins_sums_units_to_copper():
    assert parse_coins(["60 gp"]) == 6000
    assert parse_coins(["1 pp", "2 gp", "5 sp", "3 cp"]) == 1000 + 200 + 50 + 3
    assert parse_coins(["1,250 gp"]) == 125000


def test_parse_coins_rejects_unreadable_text():
    assert parse_coins([]) is None
    assert parse_coins(["lots"]) is None


def test_first_int_reads_quantity_not_substrings():
    assert first_int("× 3") == 3
    assert first_int("25 sheet") == 25
    assert first_int("× 10") == 10
    assert first_int(None) is None
    assert first_int("none") is None


def test_wait_until_returns_value_or_none():
    assert wait_until(lambda: "ok", timeout=1) == "ok"
    assert wait_until(lambda: False, timeout=0.2, interval=0.05) is None
