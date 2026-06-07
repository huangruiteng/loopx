#!/usr/bin/env python3
"""Smoke-test restarted-worker actionability from compact benchmark history."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
NOTE = TOPIC_DIR / "benchmark-restart-actionability-v0.md"
README = TOPIC_DIR / "README.md"
HISTORY_SMOKE = REPO_ROOT / "examples" / "benchmark-history-reconstructability-smoke.py"

SCHEMA = "benchmark_restart_actionability_v0"
SOURCE_SCHEMA = "benchmark_history_reconstructability_v0"
FIXTURE_COMMAND = "python3 examples/benchmark-history-reconstructability-smoke.py"
BLOCKED_EXTERNAL_ACTIONS = [
    "terminal_bench_runner",
    "harbor_runner",
    "docker",
    "codex_model_api",
    "cloud_paid_compute",
    "external_evaluator",
    "leaderboard_upload",
]
FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPEN" + "AI" + "_API" + "_KEY",
    "ANTH" + "ROPIC" + "_API" + "_KEY",
    "DAYTONA" + "_API" + "_KEY",
    "lark" + "office",
    "fei" + "shu.cn",
    "raw" + "_thread",
    "session" + "_history",
    "s" + "k-" + "example",
]


def load_history_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("benchmark_history_fixture", HISTORY_SMOKE)
    if spec is None or spec.loader is None:
        raise AssertionError("history fixture import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_action_plan(reconstructed: dict[str, Any]) -> dict[str, Any]:
    failed_gates: list[str] = []
    if reconstructed.get("schema_version") != SOURCE_SCHEMA:
        failed_gates.append("source_schema")
    if reconstructed.get("readiness") != "negative_or_control_plane_only":
        failed_gates.append("readiness")
    if reconstructed.get("authorization") != "fixture_only":
        failed_gates.append("authorization")
    if reconstructed.get("replay_decision") != "continue_fixture_replay":
        failed_gates.append("replay_decision")
    if reconstructed.get("next_run_mode") != "fixture_replay":
        failed_gates.append("next_run_mode")
    if reconstructed.get("raw_inputs_required") is not False:
        failed_gates.append("raw_inputs_required")
    if reconstructed.get("official_score", {}).get("leaderboard_evidence") is not False:
        failed_gates.append("leaderboard_evidence")
    if not reconstructed.get("stop_condition"):
        failed_gates.append("stop_condition")

    plan: dict[str, Any] = {
        "schema_version": SCHEMA,
        "source_schema_version": reconstructed.get("schema_version"),
        "fresh_worker_context": "compact_public_history_only",
        "readiness": reconstructed.get("readiness"),
        "authorization": reconstructed.get("authorization"),
        "replay_decision": reconstructed.get("replay_decision"),
        "next_run_mode": reconstructed.get("next_run_mode"),
        "official_score": reconstructed.get("official_score"),
        "control_plane_score": reconstructed.get("control_plane_score"),
        "claim_boundary": reconstructed.get("claim_boundary"),
        "must_not_claim": reconstructed.get("must_not_claim", []),
        "blocked_external_actions": BLOCKED_EXTERNAL_ACTIONS,
        "stop_condition": reconstructed.get("stop_condition"),
        "projection_change": "none",
        "raw_inputs_required": False,
    }

    if failed_gates:
        plan["selected_action"] = {
            "kind": "blocker",
            "allowed": False,
            "failed_gates": failed_gates,
            "reason": "reconstructed state is not authorized for fixture replay",
        }
    else:
        plan["selected_action"] = {
            "kind": "run_local_fixture_replay_smoke",
            "allowed": True,
            "command": FIXTURE_COMMAND,
            "validates": SOURCE_SCHEMA,
            "command_count": 1,
        }
    return plan


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 9000, len(text)


def assert_doc_contract() -> None:
    doc = NOTE.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    required = [
        SCHEMA,
        SOURCE_SCHEMA,
        "Selected Action",
        "Blocker Path",
        "Failure Rules",
        FIXTURE_COMMAND,
        "terminal_bench_runner",
        "harbor_runner",
        "codex_model_api",
        "cloud_paid_compute",
        "No real Terminal-Bench or Harbor runner execution",
    ]
    missing = [item for item in required if item not in doc]
    assert not missing, missing
    assert "benchmark-restart-actionability-v0.md" in readme, readme
    for text in (doc, readme):
        leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
        assert not leaked, leaked


def main() -> None:
    assert_doc_contract()
    history = load_history_module()
    reconstructed = history.reconstruct_next_decision(history.compact_history_rows())
    action_plan = build_action_plan(reconstructed)

    assert action_plan["schema_version"] == SCHEMA, action_plan
    assert action_plan["source_schema_version"] == SOURCE_SCHEMA, action_plan
    assert action_plan["fresh_worker_context"] == "compact_public_history_only", action_plan
    assert action_plan["readiness"] == "negative_or_control_plane_only", action_plan
    assert action_plan["authorization"] == "fixture_only", action_plan
    assert action_plan["replay_decision"] == "continue_fixture_replay", action_plan
    assert action_plan["next_run_mode"] == "fixture_replay", action_plan
    assert action_plan["selected_action"] == {
        "kind": "run_local_fixture_replay_smoke",
        "allowed": True,
        "command": FIXTURE_COMMAND,
        "validates": SOURCE_SCHEMA,
        "command_count": 1,
    }, action_plan
    assert action_plan["blocked_external_actions"] == BLOCKED_EXTERNAL_ACTIONS, action_plan
    assert "official leaderboard uplift" in action_plan["must_not_claim"], action_plan
    assert action_plan["stop_condition"] == "stop before real benchmark execution or leaderboard claims", action_plan
    assert action_plan["projection_change"] == "none", action_plan

    blocked_input = dict(reconstructed)
    blocked_input["authorization"] = "operator_gate_required"
    blocked_plan = build_action_plan(blocked_input)
    assert blocked_plan["selected_action"]["kind"] == "blocker", blocked_plan
    assert blocked_plan["selected_action"]["allowed"] is False, blocked_plan
    assert "authorization" in blocked_plan["selected_action"]["failed_gates"], blocked_plan
    assert "command" not in blocked_plan["selected_action"], blocked_plan
    assert blocked_plan["must_not_claim"] == action_plan["must_not_claim"], blocked_plan

    assert_public_safe({"action_plan": action_plan, "blocked_plan": blocked_plan})
    print(
        "benchmark-restart-actionability-smoke ok "
        f"action={action_plan['selected_action']['kind']} "
        f"blocked={blocked_plan['selected_action']['kind']} "
        f"external_blocks={len(BLOCKED_EXTERNAL_ACTIONS)}"
    )


if __name__ == "__main__":
    main()
