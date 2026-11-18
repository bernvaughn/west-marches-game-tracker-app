"""Turn `pip-audit -f json` output into SARIF and fail only on serious findings.

pip-audit has no severity filter and no SARIF output. This script adds both:

1. It reads pip-audit's JSON report.
2. For each vulnerability it asks OSV (https://api.osv.dev) for the severity.
3. It writes a SARIF file with EVERY finding, so they all show in the GitHub Security tab.
4. It exits 1 only if a finding is HIGH or CRITICAL. A finding whose severity cannot be
   found counts as HIGH, so a gap in the data never hides a real problem.

Usage: python scripts/pip_audit_to_sarif.py audit.json [--sarif results.sarif]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

OSV_URL = "https://api.osv.dev/v1/vulns/{id}"
LOCKFILE = "uv.lock"

# GitHub shows a score from 0 to 10 for each rule (the "security-severity" property).
SEVERITY_SCORE = {"CRITICAL": 9.5, "HIGH": 8.0, "MODERATE": 5.5, "LOW": 2.0}
SEVERITY_LEVEL = {"CRITICAL": "error", "HIGH": "error", "MODERATE": "warning", "LOW": "note"}
FAILING = {"CRITICAL", "HIGH"}
UNKNOWN_AS = "HIGH"  # what an unknown severity counts as

Lookup = Callable[[str], dict | None]


def osv_lookup(vuln_id: str) -> dict | None:
    """Fetch one OSV record. Returns None if OSV does not know it or cannot be reached."""
    try:
        with urllib.request.urlopen(OSV_URL.format(id=vuln_id), timeout=20) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def normalize(label: str | None) -> str | None:
    """Map a severity word from any advisory database onto CRITICAL/HIGH/MODERATE/LOW."""
    if not label:
        return None
    label = label.strip().upper()
    if label == "MEDIUM":
        label = "MODERATE"
    return label if label in SEVERITY_SCORE else None


def severity_of(vuln: dict, lookup: Lookup) -> str:
    """Best known severity for one pip-audit vulnerability record."""
    # The advisory id first, then its aliases (a PYSEC id often has a GHSA twin with a severity).
    for vuln_id in [vuln["id"], *vuln.get("aliases", [])]:
        record = lookup(vuln_id)
        if not record:
            continue
        found = normalize((record.get("database_specific") or {}).get("severity"))
        if found:
            return found
    return UNKNOWN_AS


def collect(report: dict, lookup: Lookup) -> list[dict]:
    """One flat row per vulnerability: package, version, id, severity, fix versions."""
    rows, seen = [], set()
    for dep in report.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            key = (dep["name"], dep["version"], vuln["id"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "package": dep["name"],
                    "version": dep["version"],
                    "id": vuln["id"],
                    "description": vuln.get("description") or "",
                    "fix_versions": vuln.get("fix_versions") or [],
                    "severity": severity_of(vuln, lookup),
                }
            )
    return rows


def build_sarif(rows: list[dict]) -> dict:
    """SARIF 2.1.0 with one rule per advisory and one result per affected package."""
    rules, seen = [], set()
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        rules.append(
            {
                "id": row["id"],
                "name": row["id"],
                "shortDescription": {"text": f"{row['id']} ({row['severity']})"},
                "fullDescription": {"text": row["description"] or row["id"]},
                "helpUri": f"https://osv.dev/vulnerability/{row['id']}",
                "properties": {
                    "security-severity": str(SEVERITY_SCORE[row["severity"]]),
                    "tags": ["security", "dependency"],
                },
            }
        )
    results = []
    for row in rows:
        fix = ", ".join(row["fix_versions"]) or "no fixed version yet"
        results.append(
            {
                "ruleId": row["id"],
                "level": SEVERITY_LEVEL[row["severity"]],
                "message": {
                    "text": (
                        f"{row['package']} {row['version']} has {row['id']} "
                        f"(severity {row['severity']}). Fixed in: {fix}."
                    )
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": LOCKFILE},
                            "region": {"startLine": 1},
                        }
                    }
                ],
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "pip-audit",
                        "informationUri": "https://github.com/pypa/pip-audit",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }


def failing_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["severity"] in FAILING]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("report", type=Path, help="pip-audit JSON report")
    parser.add_argument("--sarif", type=Path, default=Path("results.sarif"))
    args = parser.parse_args(argv)

    rows = collect(json.loads(args.report.read_text()), osv_lookup)
    args.sarif.write_text(json.dumps(build_sarif(rows), indent=2))

    print(f"{len(rows)} vulnerabilities found. SARIF written to {args.sarif}.")
    for row in rows:
        print(f"  {row['severity']:<8} {row['package']} {row['version']}  {row['id']}")
    bad = failing_rows(rows)
    if bad:
        print(f"FAIL: {len(bad)} are HIGH or CRITICAL. Update those packages.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
