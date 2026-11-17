"""Tests for scripts/pip_audit_to_sarif.py. No network: OSV is replaced by a dict."""

import json

from scripts import pip_audit_to_sarif as tool


def report(*vulns, name="django", version="5.2.0"):
    return {"dependencies": [{"name": name, "version": version, "vulns": list(vulns)}]}


def fake_osv(records):
    return lambda vuln_id: records.get(vuln_id)


def test_severity_comes_from_osv_and_medium_means_moderate():
    lookup = fake_osv({"PYSEC-1": {"database_specific": {"severity": "MEDIUM"}}})
    assert tool.severity_of({"id": "PYSEC-1"}, lookup) == "MODERATE"


def test_severity_falls_back_to_an_alias():
    lookup = fake_osv({"GHSA-x": {"database_specific": {"severity": "CRITICAL"}}})
    vuln = {"id": "PYSEC-2", "aliases": ["CVE-1", "GHSA-x"]}
    assert tool.severity_of(vuln, lookup) == "CRITICAL"


def test_unknown_severity_counts_as_high():
    assert tool.severity_of({"id": "PYSEC-3", "aliases": []}, fake_osv({})) == "HIGH"


def test_only_high_and_critical_fail_the_build(tmp_path):
    rows = tool.collect(
        report(
            {"id": "A", "aliases": []},
            {"id": "B", "aliases": []},
            {"id": "C", "aliases": []},
        ),
        fake_osv(
            {
                "A": {"database_specific": {"severity": "LOW"}},
                "B": {"database_specific": {"severity": "MODERATE"}},
                "C": {"database_specific": {"severity": "HIGH"}},
            }
        ),
    )
    assert [r["id"] for r in tool.failing_rows(rows)] == ["C"]
    assert tool.failing_rows(rows[:2]) == []


def test_sarif_lists_every_finding_even_the_ones_that_do_not_fail():
    rows = tool.collect(
        report({"id": "A", "fix_versions": ["5.2.1"]}, {"id": "B"}),
        fake_osv(
            {
                "A": {"database_specific": {"severity": "LOW"}},
                "B": {"database_specific": {"severity": "CRITICAL"}},
            }
        ),
    )
    sarif = tool.build_sarif(rows)
    run = sarif["runs"][0]
    assert sarif["version"] == "2.1.0"
    assert [r["ruleId"] for r in run["results"]] == ["A", "B"]
    assert [r["level"] for r in run["results"]] == ["note", "error"]
    assert "5.2.1" in run["results"][0]["message"]["text"]
    assert run["tool"]["driver"]["rules"][1]["properties"]["security-severity"] == "9.5"


def test_clean_report_gives_empty_sarif_and_exit_zero(tmp_path):
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"dependencies": [{"name": "x", "version": "1", "vulns": []}]}))
    out = tmp_path / "out.sarif"
    assert tool.main([str(audit), "--sarif", str(out)]) == 0
    assert json.loads(out.read_text())["runs"][0]["results"] == []


def test_main_exits_one_on_a_high_finding(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tool, "osv_lookup", fake_osv({"A": {"database_specific": {"severity": "HIGH"}}})
    )
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps(report({"id": "A"})))
    assert tool.main([str(audit), "--sarif", str(tmp_path / "o.sarif")]) == 1


def test_the_same_advisory_twice_for_one_package_is_reported_once():
    rows = tool.collect(report({"id": "A"}, {"id": "A"}), fake_osv({}))
    assert len(rows) == 1
