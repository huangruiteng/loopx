#!/usr/bin/env python3
"""Smoke-test the current hot-path interface budgets.

The goal is not to freeze every payload field forever. It is to make growth in
heartbeat, handoff, quota, and dashboard status payloads visible before a short
worker prompt has to absorb the extra detail.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.cli import review_packet_handoff_only_payload  # noqa: E402
from goal_harness.heartbeat_prompt import build_heartbeat_prompt  # noqa: E402
from goal_harness.quota import build_quota_should_run  # noqa: E402
from goal_harness.review_packet import build_review_packet  # noqa: E402
from goal_harness.status import collect_status  # noqa: E402


GOAL_ID = "interface-budget-goal"
CONTRACT_DOC = REPO_ROOT / "docs" / "interface-budget-contract.md"
SURFACE_BUDGETS = {
    "heartbeat_prompt_json": {
        "owner": "heartbeat automation",
        "max_json_chars": 3_500,
        "max_top_level_keys": 25,
        "budget_field": "interface_budget",
    },
    "review_packet_handoff_only_json": {
        "owner": "project-agent handoff",
        "max_json_chars": 3_000,
        "max_top_level_keys": 18,
        "budget_field": "handoff_interface_budget",
    },
    "quota_should_run_json": {
        "owner": "quota guard",
        "max_json_chars": 7_000,
        "max_top_level_keys": 45,
    },
    "dashboard_status_json": {
        "owner": "operator dashboard",
        "max_json_chars": 13_000,
        "max_top_level_keys": 20,
    },
}


def write_registry(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"

    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Interface Budget Goal\n\n"
        "## Agent Todo\n\n"
        "- [ ] Keep the handoff compact and query cold-path details only on demand.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "interface-budget-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "fixture_connected_readonly_v0",
                            "status": "connected-read-only",
                        },
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                        },
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, project


def append_run(root: Path) -> None:
    generated_at = "2026-01-01T00:05:00+00:00"
    compact = generated_at.replace("-", "").replace(":", "")
    run_dir = root / "runtime" / "goals" / GOAL_ID / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / f"{compact}-interface-budget.json"
    markdown_path = run_dir / f"{compact}-interface-budget.md"
    record = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": "state_refreshed",
        "recommended_action": "Continue compact interface-budget validation.",
        "health_check": "fixture hot-path budget run",
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text("# Fixture hot-path budget run\n", encoding="utf-8")
    (run_dir / "index.jsonl").write_text(
        json.dumps(
            {
                **record,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def json_size(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def assert_surface(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    budget = SURFACE_BUDGETS[name]
    owner = str(budget.get("owner") or "")
    assert owner, (name, budget)
    assert json_size(payload) <= int(budget["max_json_chars"]), (name, json_size(payload), budget)
    assert len(payload) <= int(budget["max_top_level_keys"]), (name, len(payload), budget)

    budget_field = budget.get("budget_field")
    if budget_field:
        interface_budget = payload.get(str(budget_field))
        assert isinstance(interface_budget, dict), (name, payload)
        assert interface_budget.get("within_budget") is True, (name, interface_budget)

    return {
        "surface": name,
        "owner": owner,
        "json_chars": json_size(payload),
        "top_level_keys": len(payload),
        "max_json_chars": budget["max_json_chars"],
        "max_top_level_keys": budget["max_top_level_keys"],
    }


def assert_contract_doc_matches_budget_table() -> None:
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    for surface, budget in SURFACE_BUDGETS.items():
        assert surface in text, surface
        assert str(budget["owner"]) in text, (surface, budget)
        assert str(budget["max_json_chars"]) in text.replace(",", "").replace("_", ""), surface
        assert str(budget["max_top_level_keys"]) in text, surface


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-hot-path-budget-") as tmp:
        root = Path(tmp)
        registry_path, project = write_registry(root)
        append_run(root)
        status_payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=str(root / "runtime"),
            scan_roots=[project],
            limit=5,
        )
        quota_payload = build_quota_should_run(status_payload, goal_id=GOAL_ID)
        review_packet = build_review_packet(status_payload, goal_id=GOAL_ID, action_kind="codex")
        handoff_payload = review_packet_handoff_only_payload(review_packet)
        heartbeat_payload = build_heartbeat_prompt(goal_id=GOAL_ID, thin=True)

    assert quota_payload["should_run"] is True, quota_payload
    assert handoff_payload["within_budget"] is True, handoff_payload
    summaries = [
        assert_surface("heartbeat_prompt_json", heartbeat_payload),
        assert_surface("review_packet_handoff_only_json", handoff_payload),
        assert_surface("quota_should_run_json", quota_payload),
        assert_surface("dashboard_status_json", status_payload),
    ]
    assert_contract_doc_matches_budget_table()

    for summary in summaries:
        print(
            "{surface}: owner={owner} json_chars={json_chars}/{max_json_chars} "
            "top_level_keys={top_level_keys}/{max_top_level_keys}".format(**summary)
        )
    print("hot-path-interface-budget-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
