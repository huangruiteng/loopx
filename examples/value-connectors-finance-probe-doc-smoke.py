#!/usr/bin/env python3
"""Prove the retired Finance connector returns extension migration guidance."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DOC = (
    ROOT
    / "docs"
    / "capabilities"
    / "value-connectors"
    / "finance-market-snapshot-probe.md"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )


def main() -> int:
    cases = (
        ("source-map", "--connector"),
        ("install-check", "--connector"),
        ("plan", "--connector-id"),
    )
    for command, selector in cases:
        completed = _run(
            "value-connectors",
            command,
            selector,
            "finance_market_snapshot",
        )
        assert completed.returncode == 0, completed.stderr
        assert '"status": "migrated_to_extension"' in completed.stdout
        assert (
            '"replacement_extension_id": "loopx-finance-value-discovery"'
            in completed.stdout
        )
        assert '"replacement_capability_id": null' in completed.stdout
        assert '"legacy_connector_executes_finance": false' in completed.stdout

    doc = " ".join(DOC.read_text(encoding="utf-8").lower().split())
    for marker in (
        "value_connector_extension_migration_v0",
        "provider source required",
        "must not recreate the old connector",
    ):
        assert marker in doc, marker

    print("value-connectors-finance-probe-doc-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
