#!/usr/bin/env python3
"""Smoke-test reading auto-research rollout events back into live evidence graphs."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research import (  # noqa: E402
    build_live_auto_research_projection,
    build_research_evidence_graph_from_rollout_events,
)
from loopx.rollout_event_log import load_rollout_events, rollout_event_log_path  # noqa: E402


PACK = REPO_ROOT / "examples/auto_research_knn_pack"
EVAL = PACK / "protected_eval.py"
CONTRACT = PACK / "research_contract.json"
CANDIDATE = PACK / "solution_candidate.py"
GOAL_ID = "loopx-auto-research-knn"


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def run_json(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert_public_safe(result.stdout)
    return json.loads(result.stdout)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def eval_result(split: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            str(EVAL),
            "--solution",
            str(CANDIDATE),
            "--split",
            split,
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def evidence_packet(dev: Path, holdout: Path) -> dict[str, Any]:
    return run_json(
        [
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "auto-research",
            "evidence",
            "--contract",
            str(CONTRACT),
            "--eval-result",
            str(dev),
            "--eval-result",
            str(holdout),
            "--hypothesis-id",
            "hyp_pack_partial_selection",
            "--todo-id",
            "todo_auto_research_pack_001",
            "--agent-id",
            "codex-side-bypass",
            "--claimed-by",
            "codex-side-bypass",
            "--mechanism-family",
            "partial_selection",
            "--hypothesis",
            "Use exact partial selection to avoid full distance sorting.",
            "--grounding-ref",
            "knn_pack_public_contract",
            "--branch-ref",
            "codex/auto-research-rollout-readpath-smoke",
        ]
    )


def append_packet(registry: Path, packet: Path) -> dict[str, Any]:
    return run_json(
        [
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--format",
            "json",
            "auto-research",
            "append-evidence",
            "--packet",
            str(packet),
        ]
    )


def frontier_projection(registry: Path) -> dict[str, Any]:
    return run_json(
        [
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--format",
            "json",
            "auto-research",
            "frontier",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            "codex-side-bypass",
        ]
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        runtime_root = temp / "runtime"
        project = temp / "project"
        project.mkdir()
        (project / "ACTIVE_GOAL_STATE.md").write_text(
            "\n".join(
                [
                    "# Active Goal State",
                    "",
                    "## Next Action",
                    "Try partial selection for exact k-NN.",
                    "",
                    "## Agent Todo",
                    "",
                    "- [ ] [P0-auto-research] Try partial selection for exact k-NN. <!-- todo_id=todo_auto_research_pack_001 claimed_by=codex-side-bypass task_class=advancement_task action_kind=run_dev_attempt -->",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        registry = temp / "registry.json"
        registry.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "common_runtime_root": str(runtime_root),
                    "goals": [
                        {
                            "id": GOAL_ID,
                            "domain": "auto_research_smoke",
                            "status": "active",
                            "repo": str(project),
                            "state_file": "ACTIVE_GOAL_STATE.md",
                            "adapter": {"kind": "fixture", "status": "connected-read-only"},
                            "coordination": {
                                "primary_agent": "codex-main-control",
                                "registered_agents": ["codex-main-control", "codex-side-bypass"],
                            },
                            "authority_sources": [],
                        }
                    ],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        dev = temp / "dev.json"
        holdout = temp / "holdout.json"
        packet_path = temp / "packet.json"
        write_json(dev, eval_result("dev"))
        write_json(holdout, eval_result("holdout"))
        write_json(packet_path, evidence_packet(dev, holdout))
        append_payload = append_packet(registry, packet_path)
        assert append_payload["appended_count"] == 3, append_payload

        rollout_events = load_rollout_events(rollout_event_log_path(runtime_root, GOAL_ID))
        graph = build_research_evidence_graph_from_rollout_events(
            goal_id=GOAL_ID,
            rollout_events=rollout_events,
        )
        assert graph["schema_version"] == "research_evidence_graph_v0", graph
        assert graph["source_kind"] == "loopx_rollout_event_log", graph
        assert graph["hypothesis_count"] == 1, graph
        assert graph["evidence_event_count"] == 2, graph
        assert graph["metric"]["name"] == "deterministic_speedup", graph
        assert graph["baseline_metric"] == 1.0, graph
        assert graph["best_dev_metric"] and graph["best_dev_metric"] > 1.0, graph
        assert graph["best_holdout_metric"] and graph["best_holdout_metric"] > 1.0, graph
        assert graph["holdout_improved"] is True, graph
        assert graph["nodes"][0]["hypothesis_id"] == "hyp_pack_partial_selection", graph
        assert_public_safe(graph)

        live_payload = build_live_auto_research_projection(
            goal_id=GOAL_ID,
            agent_id="codex-side-bypass",
            quota_payload={
                "ok": True,
                "agent_lane_next_action": {
                    "todo_id": "todo_auto_research_pack_001",
                    "title": "Try partial selection for exact k-NN",
                    "claimed_by": "codex-side-bypass",
                    "status": "open",
                    "task_class": "advancement_task",
                    "action_kind": "run_dev_attempt",
                },
                "capability_gate": {
                    "runnable_candidates": [
                        {
                            "todo_id": "todo_auto_research_pack_001",
                            "title": "Try partial selection for exact k-NN",
                            "claimed_by": "codex-side-bypass",
                            "status": "open",
                            "task_class": "advancement_task",
                            "action_kind": "run_dev_attempt",
                        }
                    ],
                    "blocked_candidates": [],
                },
            },
            rollout_events=rollout_events,
        )
        assert live_payload["evidence_graph"]["source_kind"] == "loopx_rollout_event_log", live_payload
        assert live_payload["evidence_graph"]["evidence_event_count"] == 2, live_payload
        assert live_payload["showcase_projection"]["best_holdout_metric"] == graph["best_holdout_metric"], live_payload
        assert live_payload["showcase_projection"]["decentralized_pattern"] == (
            "todo_backed_live_frontier_rollout_evidence_graph"
        ), live_payload
        assert live_payload["public_boundary"]["source"] == "live_quota_status_and_rollout_event_log", live_payload
        assert_public_safe(live_payload)

        cli_payload = frontier_projection(registry)
        assert cli_payload["ok"], cli_payload
        assert cli_payload["evidence_graph"]["source_kind"] == "loopx_rollout_event_log", cli_payload
        assert cli_payload["evidence_graph"]["evidence_event_count"] == 2, cli_payload
        assert cli_payload["showcase_projection"]["best_holdout_metric"] == graph["best_holdout_metric"], cli_payload
        assert_public_safe(cli_payload)

    print("auto-research-rollout-readpath-smoke ok")


if __name__ == "__main__":
    main()
