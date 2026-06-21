#!/usr/bin/env python3
"""Smoke-test Terminal-Bench treatment arm taxonomy boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-treatment-arm-taxonomy-v0.md"
README = TOPIC_DIR / "README.md"

ARMS = (
    "codex_goal_mode",
    "codex_loopx",
    "hardened_codex_calibration",
    "passive_loopx_observer",
)

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "DOUBAO" + "_MODEL=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
    "-----BEGIN",
]

REQUIRED_SNIPPETS = [
    "Terminal-Bench Treatment Arm Taxonomy V0",
    "codex_goal_mode",
    "codex_loopx",
    "hardened_codex_calibration",
    "passive_loopx_observer",
    "primary_paired_baseline",
    "calibration_only",
    "codex_runtime_goal_tool_calls",
    "loopx_cli_calls",
    "loopx_state_reads",
    "loopx_state_writes",
    "harness_skill_or_packet_injected",
    "prompt_packet_only_no_cli_bridge",
    "codex_runtime_goal_tool_calls=2",
    "loopx_cli_calls=0",
    "create_goal",
    "update_goal",
    "LoopX Access Packet",
    "python3 examples/terminal-bench-treatment-arm-taxonomy-smoke.py",
]


def taxonomy_payload() -> dict[str, Any]:
    return {
        "schema_version": "terminal_bench_treatment_arm_taxonomy_v0",
        "arms": {
            "codex_goal_mode": {
                "loopx_inside_case": False,
                "official_score_comparable_to_native_codex": False,
                "uses_codex_runtime_goal_tools": True,
                "uses_loopx_interfaces": False,
                "codex_goal_mode_enabled": True,
                "primary_paired_baseline": True,
                "calibration_only": False,
            },
            "codex_loopx": {
                "loopx_inside_case": True,
                "official_score_comparable_to_native_codex": False,
                "uses_codex_runtime_goal_tools": "allowed_but_separately_counted",
                "uses_loopx_interfaces": "requires_cli_bridge_or_trace",
                "codex_goal_mode_enabled": True,
                "primary_paired_baseline": False,
                "calibration_only": False,
                "current_v0_interface_surface": "prompt_packet_only_no_cli_bridge",
                "current_v0_cli_bridge_available": False,
            },
            "hardened_codex_calibration": {
                "loopx_inside_case": False,
                "official_score_comparable_to_native_codex": False,
                "official_score_comparable_to_loopx_treatment": False,
                "uses_codex_runtime_goal_tools": False,
                "uses_loopx_interfaces": False,
                "codex_goal_mode_enabled": False,
                "primary_paired_baseline": False,
                "calibration_only": True,
                "task_prompt_changed": False,
            },
            "passive_loopx_observer": {
                "loopx_inside_case": False,
                "official_score_comparable_to_native_codex": True,
                "uses_codex_runtime_goal_tools": False,
                "uses_loopx_interfaces": "outside_case_only",
            },
        },
        "first_managed_sample_reclassification": {
            "prompt_policy_injected": True,
            "codex_runtime_goal_tool_calls": {
                "create_goal": 1,
                "update_goal": 1,
                "total": 2,
            },
            "loopx_cli_calls": 0,
            "loopx_state_reads": 0,
            "loopx_state_writes": 0,
            "harness_skill_or_packet_injected": False,
            "case_result_writeback": "runner_only",
            "correct_arm": "codex_goal_mode",
            "incorrect_arm": "codex_loopx",
        },
        "codex_loopx_required_packet": [
            "loopx_interface_surface",
            "loopx_cli_bridge_available",
            "declared_loopx_interface_commands",
            "when_to_call_status_todo_history_check_or_writeback",
            "public_safety_boundaries",
            "compact_counter_reporting",
        ],
        "real_run": False,
        "submit_eligible": False,
    }


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 18000, len(text)


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "terminal-bench-treatment-arm-taxonomy-v0.md" in readme, readme
    assert_public_safe(text)

    payload = taxonomy_payload()
    assert tuple(payload["arms"]) == ARMS, payload
    codex_goal = payload["arms"]["codex_goal_mode"]
    harness = payload["arms"]["codex_loopx"]
    calibration = payload["arms"]["hardened_codex_calibration"]
    passive = payload["arms"]["passive_loopx_observer"]
    sample = payload["first_managed_sample_reclassification"]

    assert codex_goal["codex_goal_mode_enabled"] is True, codex_goal
    assert codex_goal["primary_paired_baseline"] is True, codex_goal
    assert codex_goal["calibration_only"] is False, codex_goal
    assert codex_goal["uses_codex_runtime_goal_tools"] is True, codex_goal
    assert codex_goal["uses_loopx_interfaces"] is False, codex_goal
    assert harness["loopx_inside_case"] is True, harness
    assert harness["codex_goal_mode_enabled"] is True, harness
    assert harness["primary_paired_baseline"] is False, harness
    assert harness["calibration_only"] is False, harness
    assert harness["uses_loopx_interfaces"] == "requires_cli_bridge_or_trace", harness
    assert harness["current_v0_interface_surface"] == "prompt_packet_only_no_cli_bridge", harness
    assert harness["current_v0_cli_bridge_available"] is False, harness
    assert calibration["calibration_only"] is True, calibration
    assert calibration["primary_paired_baseline"] is False, calibration
    assert calibration["codex_goal_mode_enabled"] is False, calibration
    assert calibration["task_prompt_changed"] is False, calibration
    assert calibration["uses_loopx_interfaces"] is False, calibration
    assert calibration["official_score_comparable_to_native_codex"] is False, calibration
    assert calibration["official_score_comparable_to_loopx_treatment"] is False, calibration
    assert passive["uses_loopx_interfaces"] == "outside_case_only", passive
    assert sample["codex_runtime_goal_tool_calls"]["total"] == 2, sample
    assert sample["loopx_cli_calls"] == 0, sample
    assert sample["loopx_state_reads"] == 0, sample
    assert sample["loopx_state_writes"] == 0, sample
    assert sample["harness_skill_or_packet_injected"] is False, sample
    assert sample["correct_arm"] == "codex_goal_mode", sample
    assert sample["incorrect_arm"] == "codex_loopx", sample
    assert payload["real_run"] is False, payload
    assert payload["submit_eligible"] is False, payload
    assert_public_safe(payload)
    print("terminal-bench-treatment-arm-taxonomy-smoke ok arms=4 sample_cli_calls=0")


if __name__ == "__main__":
    main()
