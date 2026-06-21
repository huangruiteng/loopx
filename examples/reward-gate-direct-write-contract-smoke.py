#!/usr/bin/env python3
"""Smoke-test the minimal reward/gate direct-write planning contract."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.feedback import append_human_reward, compact_reward  # noqa: E402
from loopx.operator_gate import OPERATOR_GATE_RESUME_CONTRACT_VERSION, record_operator_gate  # noqa: E402


GOAL_ID = "reward-gate-direct-write-goal"
RUN_GENERATED_AT = "2026-01-01T00:00:00+00:00"
CONTRACT_DOC = REPO_ROOT / "docs" / "reward-gate-direct-write-contract.md"


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    runtime_root = root / "runtime"
    project = root / "project"
    project.mkdir(parents=True)
    state_file = project / "ACTIVE_GOAL_STATE.md"
    state_file.write_text(
        "---\n"
        "status: connected-read-only\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Reward Gate Direct Write Goal\n\n"
        "## Progress Ledger\n\n",
        encoding="utf-8",
    )

    run_dir = runtime_root / "goals" / GOAL_ID / "runs"
    run_dir.mkdir(parents=True)
    json_artifact = run_dir / "run.json"
    markdown_artifact = run_dir / "run.md"
    json_artifact.write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    markdown_artifact.write_text("# Smoke Run\n", encoding="utf-8")
    (run_dir / "index.jsonl").write_text(
        json.dumps(
            {
                "generated_at": RUN_GENERATED_AT,
                "goal_id": GOAL_ID,
                "classification": "adapter_inspected",
                "recommended_action": "judge whether the route should continue",
                "health_check": "fixture run",
                "json_path": str(json_artifact),
                "markdown_path": str(markdown_artifact),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    registry = root / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "state_file": "ACTIVE_GOAL_STATE.md",
                        "domain": "reward-gate-direct-write-smoke",
                        "status": "connected-read-only",
                        "adapter": {
                            "kind": "smoke",
                            "status": "connected-read-only",
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry, runtime_root, state_file


def assert_public_decision_contract(kind: str, payload: dict[str, Any]) -> None:
    assert payload["goal_id"] == GOAL_ID, payload
    assert payload["dry_run"] is True, payload
    assert payload["appended"] is False, payload
    assert payload.get("error") in (None, ""), payload
    assert kind in {"human_reward", "operator_gate"}, kind


def assert_reward_preview(registry: Path, runtime_root: Path, state_file: Path) -> None:
    reward = compact_reward(
        recorded_at="2026-01-01T00:10:00+00:00",
        decision="continue_route",
        reward="positive",
        reason_summary="validated route improved enough to keep exploring",
        follow_up="let the project agent read history before the next route check",
    )
    payload = append_human_reward(
        registry_path=registry,
        runtime_root_override=str(runtime_root),
        goal_id=GOAL_ID,
        run_generated_at=RUN_GENERATED_AT,
        reward=reward,
        dry_run=True,
        state_file_override=state_file,
        write_active_state_summary=True,
    )
    assert_public_decision_contract("human_reward", payload)
    assert payload["selected_run"]["generated_at"] == RUN_GENERATED_AT, payload
    assert payload["human_reward"]["reward"] == "positive", payload
    assert payload["active_state_update"]["would_write"] is True, payload
    assert payload["active_state_update"]["written"] is False, payload
    visibility = payload["project_agent_visibility"]
    assert visibility["source_of_truth"] == "run_bound_human_reward_overlay", visibility
    assert visibility["history_command"] == f"loopx history --goal-id {GOAL_ID} --limit 3", visibility
    assert "human_reward" not in state_file.read_text(encoding="utf-8"), "dry-run must not write state"


def assert_operator_gate_preview(registry: Path, runtime_root: Path) -> None:
    payload = record_operator_gate(
        registry_path=registry,
        runtime_root_override=str(runtime_root),
        goal_id=GOAL_ID,
        gate="handoff_opt_in",
        decision="approve",
        operator_question="Approve the public-safe handoff for the fixture goal?",
        reason_summary="handoff evidence is compact and public-safe",
        follow_up="forward only the approved handoff packet",
        agent_command=f"loopx review-packet --goal-id {GOAL_ID} --handoff-only",
        recommended_action=None,
        recorded_at="2026-01-01T00:20:00+00:00",
        dry_run=True,
        sync_global=False,
    )
    assert_public_decision_contract("operator_gate", payload)
    assert payload["classification"] == "operator_gate_approved", payload
    gate = payload["operator_gate"]
    assert gate["gate"] == "handoff_opt_in", gate
    assert gate["decision"] == "approve", gate
    assert gate["agent_command"].endswith("--handoff-only"), gate
    contract = payload["operator_gate_resume_contract"]
    assert contract["version"] == OPERATOR_GATE_RESUME_CONTRACT_VERSION, contract
    assert contract["gate_id"] == "handoff_opt_in", contract
    assert "re-read current decision-point authority" in contract["freshness_check"], contract
    assert "do not restore" in contract["migration_or_rebase_result"], contract


def assert_contract_doc() -> None:
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    required = [
        "decision_write_contract_v0",
        "decision_kind",
        "target_ref",
        "preview_id",
        "source_of_truth",
        "write_effect",
        "project_agent_visibility",
        "run_bound_human_reward_overlay",
        "operator_gate_decision_run",
        "--enable-reward-write-api",
        "There is no dashboard `operator_gate` apply endpoint",
        "operator_gate_resume_contract",
        "disabled-by-default",
    ]
    for marker in required:
        assert marker in text, marker


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-reward-gate-write-") as raw_tmp:
        registry, runtime_root, state_file = write_fixture(Path(raw_tmp))
        assert_reward_preview(registry, runtime_root, state_file)
        assert_operator_gate_preview(registry, runtime_root)
        assert_contract_doc()

    print("reward-gate-direct-write-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
