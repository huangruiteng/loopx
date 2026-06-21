#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.operator_gate import OPERATOR_GATE_RESUME_CONTRACT_VERSION, record_operator_gate  # noqa: E402


def write_registry(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    goal_id = "checkpointed-gate-goal"
    state_file = f".codex/goals/{goal_id}/ACTIVE_GOAL_STATE.md"
    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: planned-high-complexity\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Checkpointed Gate Goal\n",
        encoding="utf-8",
    )
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": goal_id,
                        "repo": str(project),
                        "state_file": state_file,
                        "domain": "smoke",
                        "status": "planned-high-complexity",
                        "adapter": {"kind": "smoke_read_only_map", "status": "planned"},
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-operator-gate-resume-contract-") as tmp:
        root = Path(tmp)
        registry = write_registry(root)
        payload = record_operator_gate(
            registry_path=registry,
            runtime_root_override=None,
            goal_id="checkpointed-gate-goal",
            gate="read_only_map_opt_in",
            decision="approve",
            operator_question=None,
            reason_summary="approve read-only dry-run after checking the public smoke fixture",
            follow_up="project agent must stop before write or production action",
            agent_command=None,
            recommended_action=None,
            recorded_at="2026-01-01T00:00:01+00:00",
            dry_run=True,
            sync_global=False,
        )
        contract = payload["operator_gate_resume_contract"]
        assert payload["ok"] is True, payload
        assert payload["dry_run"] is True, payload
        assert payload["appended"] is False, payload
        assert contract["version"] == OPERATOR_GATE_RESUME_CONTRACT_VERSION, contract
        assert contract["goal_id"] == "checkpointed-gate-goal", contract
        assert contract["gate_id"] == "read_only_map_opt_in", contract
        assert contract["operator_decision"] == "approve", contract
        assert contract["interrupt_payload"]["choices"] == ["approve", "defer", "reject"], contract
        assert "decision_point_rebase_only" in contract["migration_or_rebase_result"], contract
        assert "whole repo/worktree" in contract["migration_or_rebase_result"], contract
        assert "quota" in contract["freshness_check"], contract
        assert "side effects" in contract["validation_after_resume"], contract

    print("operator-gate-resume-contract-smoke ok")


if __name__ == "__main__":
    main()
