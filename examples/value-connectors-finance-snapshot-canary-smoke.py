#!/usr/bin/env python3
"""Smoke-test the dry-run finance market snapshot canary."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

FORBIDDEN_VALUES = [
    "raw provider payload",
    "private portfolio holding",
    "account id should stay gated",
    "trading intent should stay gated",
    "sensitive-value",
]


def assert_public_safe(payload: dict[str, Any] | str) -> None:
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"payload matched private pattern {pattern.pattern!r}")
    leaked = [value for value in FORBIDDEN_VALUES if value in text]
    assert not leaked, leaked


def run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    eastmoney_payload = {
        "data": {
            "f57": "600519",
            "f58": "贵州茅台",
            "f43": 141234,
            "f169": 123,
            "f170": 9,
            "f47": 123456,
            "f48": 987654321,
            "f60": 141111,
            "f86": 1783480845,
            "f116": 1750000000000,
            "raw": "raw provider payload",
            "account_id": "account id should stay gated",
        }
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        payload_path = Path(tmpdir) / "eastmoney.json"
        payload_path.write_text(json.dumps(eastmoney_payload), encoding="utf-8")
        snapshot = json.loads(
            run_cli(
                [
                    "--format",
                    "json",
                    "value-connectors",
                    "finance-market-snapshot",
                    "--symbol",
                    "sh600519",
                    "--metadata-json",
                    str(payload_path),
                    "--thesis-id",
                    "ai_pcb_chain_bottom_reversal",
                    "--thesis",
                    "AI hardware PCB chain bottom reversal is worth human review",
                ]
            ).stdout
        )

    assert snapshot["ok"] is True, snapshot
    assert snapshot["schema_version"] == "finance_market_snapshot_canary_packet_v0", snapshot
    assert snapshot["connector_id"] == "finance_market_snapshot", snapshot
    assert snapshot["external_reads_performed"] is False, snapshot
    assert snapshot["external_writes_performed"] is False, snapshot
    assert snapshot["raw_provider_payload_recorded"] is False, snapshot
    assert snapshot["private_source_content_read"] is False, snapshot
    assert snapshot["non_investment_advice"] is True, snapshot
    assert snapshot["autotrade_allowed"] is False, snapshot
    assert snapshot["validation"]["ok"] is True, snapshot
    assert snapshot["validation"]["gated_provider_field_count"] == 2, snapshot
    assert snapshot["research_context"]["human_decision_owner"] is True, snapshot
    assert snapshot["research_context"]["thesis_id"] == "ai_pcb_chain_bottom_reversal", snapshot
    assert snapshot["research_context"]["supports_or_challenges"] == "manual_review_required", snapshot

    quote = snapshot["snapshots"][0]
    assert quote["symbol"] == "sh600519", quote
    assert quote["source_id"] == "eastmoney_public_quote", quote
    assert quote["freshness_label"] == "source_unverified", quote
    assert quote["source_url"] == "https://quote.eastmoney.com/sh600519.html", quote
    assert quote["quote_fields"]["name"] == "贵州茅台", quote
    assert quote["quote_fields"]["latest_price"] == 1412.34, quote
    assert quote["quote_fields"]["pct_change"] == 0.09, quote
    assert quote["observed_at"] == "2026-07-08T00:00:00Z", quote
    assert "provider_terms" in quote["missing_or_unverified"], quote
    assert "official_field_map" in quote["missing_or_unverified"], quote
    assert quote["raw_provider_payload_recorded"] is False, quote
    assert_public_safe(snapshot)

    markdown = run_cli(
        [
            "value-connectors",
            "finance-market-snapshot",
            "--symbol",
            "sh600519",
            "--thesis",
            "AI hardware PCB chain bottom reversal is worth human review",
        ]
    ).stdout
    assert "LoopX Finance Market Snapshot Canary" in markdown, markdown
    assert "non_investment_advice: `True`" in markdown, markdown
    assert "manual_review_required" in markdown, markdown
    assert_public_safe(markdown)

    for gated_source in [
        "futu_opend",
        "private_portfolio",
        "paid_data",
        "trading",
        "captcha",
        "credential",
    ]:
        rejected = run_cli(
            [
                "--format",
                "json",
                "value-connectors",
                "finance-market-snapshot",
                "--symbol",
                "sh600519",
                "--source",
                gated_source,
            ],
            check=False,
        )
        assert rejected.returncode == 1, (gated_source, rejected)
        rejected_payload = json.loads(rejected.stdout)
        assert rejected_payload["ok"] is False, rejected_payload
        assert rejected_payload["schema_version"] == "finance_market_snapshot_canary_error_v0"
        assert "requires an exact user gate" in rejected_payload["error"], rejected_payload
        assert rejected_payload["external_reads_performed"] is False, rejected_payload
        assert rejected_payload["external_writes_performed"] is False, rejected_payload
        assert_public_safe(rejected_payload)

    unknown_symbol = run_cli(
        [
            "--format",
            "json",
            "value-connectors",
            "finance-market-snapshot",
            "--symbol",
            "sh601398",
        ],
        check=False,
    )
    assert unknown_symbol.returncode == 1, unknown_symbol
    unknown_payload = json.loads(unknown_symbol.stdout)
    assert unknown_payload["ok"] is False, unknown_payload
    assert "symbol must be one of" in unknown_payload["error"], unknown_payload
    assert_public_safe(unknown_payload)

    print("value-connectors-finance-snapshot-canary-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
