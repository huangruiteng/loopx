#!/usr/bin/env python3
"""Smoke-test status watch routing uses explicit attributes, not monitor names."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.status import goal_attention  # noqa: E402


def attention_for(run: dict[str, object]) -> dict[str, object]:
    item = goal_attention(
        {
            "id": "status-watch-routing-fixture",
            "registry_member": True,
            "adapter_status": "connected-read-only",
            "latest_status_run": run,
            "latest_runs": [run],
        }
    )
    assert item is not None, run
    return item


def main() -> int:
    product_monitor_run = {
        "classification": "monitor_due_scheduler_todos_planned",
        "recommended_action": "Implement monitor scheduler runtime routing.",
        "json_exists": True,
        "markdown_exists": True,
        "delivery_outcome": "surface_only",
    }
    product_item = attention_for(product_monitor_run)
    assert product_item["waiting_on"] == "codex", product_item
    assert product_item["severity"] == "action", product_item

    explicit_external_run = {
        "classification": "runtime_result_pending",
        "waiting_on": "external_evidence",
        "recommended_action": "Observe the external worker result.",
        "json_exists": True,
        "markdown_exists": True,
        "delivery_outcome": "surface_only",
    }
    explicit_item = attention_for(explicit_external_run)
    assert explicit_item["waiting_on"] == "external_evidence", explicit_item
    assert explicit_item["severity"] == "watch", explicit_item

    legacy_external_run = {
        "classification": "external_evidence_observation_contract_validated_v0",
        "recommended_action": "Observe the external result channel.",
        "json_exists": True,
        "markdown_exists": True,
        "delivery_outcome": "surface_only",
    }
    legacy_item = attention_for(legacy_external_run)
    assert legacy_item["waiting_on"] == "external_evidence", legacy_item
    assert legacy_item["severity"] == "watch", legacy_item

    print("status-watch-routing-attribute-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
