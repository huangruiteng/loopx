#!/usr/bin/env python3
"""Smoke-test compact live evidence capture for visible auto-research lanes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "loopx-auto-research-demo"
AGENT_ID = "codex-side-bypass"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def run_cli(
    args: list[str],
    *,
    registry: Path,
    runtime_root: Path,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime_root),
            "--format",
            "json",
            *args,
        ],
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def write_demo_contract_and_eval(workspace: Path) -> tuple[Path, Path, Path]:
    contract_path = workspace / "research-contract.public.json"
    dev_path = workspace / "dev-result.public.json"
    holdout_path = workspace / "holdout-result.public.json"
    contract_path.write_text(
        json.dumps(
            {
                "schema_version": "research_contract_v0",
                "goal_id": GOAL_ID,
                "research_objective": "Validate compact visible-lane evidence capture.",
                "editable_scope": ["candidate_strategy", "todo_handoff"],
                "protected_scope": ["metric_definition", "holdout_split"],
                "metric": {
                    "name": "demo_quality_score",
                    "direction": "maximize",
                    "baseline": 1.0,
                },
                "dev_eval": "builtin lightweight metric evaluator on dev split",
                "holdout_eval": "builtin lightweight metric evaluator on holdout split",
                "promotion_policy": "dev_and_holdout_improved",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for path, split, value in (
        (dev_path, "dev", 4.0),
        (holdout_path, "holdout", 4.5),
    ):
        path.write_text(
            json.dumps(
                {
                    "schema_version": "auto_research_lightweight_eval_result_v0",
                    "split": split,
                    "metric": {
                        "name": "demo_quality_score",
                        "value": value,
                        "direction": "maximize",
                        "baseline": 1.0,
                    },
                    "eval_status": "scored",
                    "primary_metric_status": "improved",
                    "artifact_refs": [f"public_metric:{split}:state_a2a_round"],
                    "protected_scope_clean": True,
                    "no_upload": True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return contract_path, dev_path, holdout_path


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        workspace = temp / "workspace"
        workspace.mkdir()
        registry = temp / "registry.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )

        contract_path, dev_path, holdout_path = write_demo_contract_and_eval(workspace)

        evidence = run_cli(
            [
                "auto-research",
                "evidence",
                "--contract",
                str(contract_path),
                "--eval-result",
                str(dev_path),
                "--eval-result",
                str(holdout_path),
                "--hypothesis-id",
                "hyp_live_lane_state_a2a_round",
                "--todo-id",
                "todo_live_lane_state_a2a_round",
                "--agent-id",
                AGENT_ID,
                "--claimed-by",
                AGENT_ID,
                "--mechanism-family",
                "state_a2a_iteration",
                "--hypothesis",
                "Use a small state-mediated handoff loop to improve the shared candidate.",
                "--grounding-ref",
                "kernel:state_a2a_metric_demo",
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
        )
        evidence_payload = json.loads(evidence.stdout)
        evidence_path = workspace / "evidence.public.json"
        evidence_path.write_text(json.dumps(evidence_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        append = run_cli(
            [
                "auto-research",
                "append-evidence",
                "--packet",
                str(evidence_path),
                "--output",
                "append-result.public.json",
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
        )
        append_payload = json.loads(append.stdout)
        append_path = workspace / "append-result.public.json"
        assert append_path.is_file(), append_payload
        assert json.loads(append_path.read_text(encoding="utf-8")) == append_payload, append_payload
        assert append_payload["appended_count"] == 3, append_payload

        live_path = workspace / "live-codex-e2e-evidence.public.json"
        rejected = run_cli(
            [
                "auto-research",
                "capture-live-evidence",
                "--packet",
                str(evidence_path),
                "--append-result",
                str(append_path),
                "--agent-id",
                AGENT_ID,
                "--lane-count",
                "3",
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
            check=False,
        )
        assert rejected.returncode == 1, rejected.stdout
        rejected_payload = json.loads(rejected.stdout)
        assert rejected_payload["ok"] is False, rejected_payload
        assert "accepted visible lanes" in rejected_payload["error"], rejected_payload
        assert_public_safe(rejected_payload)

        capture = run_cli(
            [
                "auto-research",
                "capture-live-evidence",
                "--packet",
                str(evidence_path),
                "--append-result",
                str(append_path),
                "--agent-id",
                AGENT_ID,
                "--lane-count",
                "3",
                "--visible-lanes-accepted",
                "--output",
                str(live_path),
                "--execute",
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
        )
        live_payload = json.loads(capture.stdout)
        assert live_path.is_file(), live_payload
        assert json.loads(live_path.read_text(encoding="utf-8")) == live_payload, live_payload
        assert live_payload["schema_version"] == "auto_research_live_codex_lane_e2e_evidence_v0", live_payload
        assert live_payload["source"] == "live_codex_lane_output", live_payload
        assert live_payload["goal_id"] == GOAL_ID, live_payload
        assert live_payload["agent_id"] == AGENT_ID, live_payload
        assert live_payload["visible_lanes"]["accepted"] is True, live_payload
        assert live_payload["lane_evidence"]["append_status"] == "appended_to_loopx_state", live_payload
        assert live_payload["lane_evidence"]["evidence_event_count"] == 2, live_payload
        assert live_payload["lane_evidence"]["dev_metric"] == 4.0, live_payload
        assert live_payload["lane_evidence"]["holdout_metric"] == 4.5, live_payload
        assert_public_safe(live_payload)

        handoff_packet = json.loads(evidence_path.read_text(encoding="utf-8"))
        handoff_packet["hypothesis"]["claimed_by"] = "codex-main-control"
        handoff_path = workspace / "handoff-evidence.public.json"
        handoff_path.write_text(
            json.dumps(handoff_packet, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        wrong_handoff_agent = run_cli(
            [
                "auto-research",
                "capture-live-evidence",
                "--packet",
                str(handoff_path),
                "--append-result",
                str(append_path),
                "--agent-id",
                "codex-main-control",
                "--lane-count",
                "3",
                "--visible-lanes-accepted",
                "--execute",
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
            check=False,
        )
        assert wrong_handoff_agent.returncode == 1, wrong_handoff_agent.stdout
        wrong_payload = json.loads(wrong_handoff_agent.stdout)
        assert "evidence event agent_id" in wrong_payload["error"], wrong_payload
        assert_public_safe(wrong_payload)

        handoff_live_path = workspace / "handoff-live-codex-e2e-evidence.public.json"
        handoff_capture = run_cli(
            [
                "auto-research",
                "capture-live-evidence",
                "--packet",
                str(handoff_path),
                "--append-result",
                str(append_path),
                "--agent-id",
                AGENT_ID,
                "--lane-count",
                "3",
                "--visible-lanes-accepted",
                "--output",
                str(handoff_live_path),
                "--execute",
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
        )
        handoff_live_payload = json.loads(handoff_capture.stdout)
        assert handoff_live_path.is_file(), handoff_live_payload
        assert handoff_live_payload["agent_id"] == AGENT_ID, handoff_live_payload
        assert handoff_live_payload["lane_evidence"]["dev_metric"] == 4.0, handoff_live_payload
        assert handoff_live_payload["lane_evidence"]["holdout_metric"] == 4.5, handoff_live_payload
        assert_public_safe(handoff_live_payload)

        claimed = run_cli(
            [
                "auto-research",
                "demo-e2e",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--execute",
                "--headless",
                "--live-evidence",
                str(live_path),
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
        )
        claimed_payload = json.loads(claimed.stdout)
        proof = claimed_payload["visible_worker_proof"]
        live = claimed_payload["live_worker_evidence"]
        assert proof["lane_authored_evidence_loaded"] is True, claimed_payload
        assert proof["visible_lanes_launched"] is True, claimed_payload
        assert proof["visible_lanes_accepted"] is True, claimed_payload
        assert proof["evidence_source"] == "live_worker_evidence", claimed_payload
        assert live["loaded"] is True, claimed_payload
        assert live["source"] == "live_codex_lane_output", claimed_payload
        assert live["evidence_event_count"] == 2, claimed_payload
        assert live["dev_metric"] == 4.0, claimed_payload
        assert live["holdout_metric"] == 4.5, claimed_payload
        assert "live_codex_e2e" not in claimed_payload, claimed_payload
        assert "claim_summary" not in claimed_payload, claimed_payload
        assert_public_safe(claimed_payload)

    print("auto-research-live-evidence-capture-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
