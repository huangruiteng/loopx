#!/usr/bin/env python3
"""Smoke-test the minimal auto-research decision kernel.

The kernel must stay a small evaluator-agnostic decision loop. Public demo and
worker-loop code may wrap it, but the kernel itself must not ship a built-in
protected-eval replay or a user-facing shortcut that looks like a full E2E run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.auto_research import (  # noqa: E402
    LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION,
    lightweight_hypothesis,
    run_lightweight_auto_research,
)


KERNEL = REPO_ROOT / "loopx/capabilities/auto_research/kernel.py"
CORE = REPO_ROOT / "loopx/capabilities/auto_research/core.py"
INIT = REPO_ROOT / "loopx/capabilities/auto_research/__init__.py"
EVIDENCE_PACKET = REPO_ROOT / "loopx/capabilities/auto_research/evidence_packet.py"
ROLLOUT_APPEND = REPO_ROOT / "loopx/capabilities/auto_research/rollout_append.py"
LIVE_EVIDENCE = REPO_ROOT / "loopx/capabilities/auto_research/live_evidence.py"
RESEARCH_STATE = REPO_ROOT / "loopx/capabilities/auto_research/research_state.py"
HUMAN_VIEW = REPO_ROOT / "loopx/capabilities/auto_research/human_view.py"
WORKER_RUNTIME = REPO_ROOT / "loopx/capabilities/auto_research/worker_runtime.py"
CLI = REPO_ROOT / "loopx/capabilities/auto_research/cli.py"

KERNEL_FORBIDDEN_MARKERS = [
    "legacy" + "_core",
    "demo_e2e",
    "worker_runtime",
    "visible_multi_agent_launcher",
    "protected_eval",
    "quickstart",
    "knn",
    "showcase",
    "tmux",
    "codex",
]

def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "byte" + "dance",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
        "deterministic_" + "protected_eval_kernel",
        "protected_eval_result",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def assert_positive_result(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == LIGHTWEIGHT_AUTO_RESEARCH_RESULT_SCHEMA_VERSION, payload
    assert payload["candidate_count"] == 2, payload
    assert payload["dev_round_count"] == 2, payload
    assert payload["evidence_event_count"] == 3, payload
    assert payload["selected_hypothesis_id"] == "hyp_partial_selection", payload
    assert payload["decision"] == "validated_positive", payload
    assert payload["dev_metric"] == 4.0, payload
    assert payload["holdout_metric"] == 4.5, payload
    assert {event["result_source"] for event in payload["evidence"]} == {
        "injected_metric_evaluator"
    }, payload
    assert payload["public_boundary"]["raw_logs_recorded"] is False, payload
    assert payload["public_boundary"]["private_artifacts_recorded"] is False, payload
    assert_public_safe(payload)


def assert_kernel_boundary() -> None:
    kernel_text = KERNEL.read_text(encoding="utf-8")
    core_text = CORE.read_text(encoding="utf-8")
    init_text = INIT.read_text(encoding="utf-8")
    lightweight_surface = kernel_text + "\n" + core_text + "\n" + init_text
    assert len(kernel_text.splitlines()) <= 220
    assert len(core_text.splitlines()) <= 40
    assert "run_builtin_lightweight_demo" not in lightweight_surface
    leaked_markers = [
        marker
        for marker in KERNEL_FORBIDDEN_MARKERS
        if marker.lower() in lightweight_surface.lower()
    ]
    assert not leaked_markers, leaked_markers


def assert_evidence_packet_boundary() -> None:
    evidence_text = EVIDENCE_PACKET.read_text(encoding="utf-8")
    rollout_text = ROLLOUT_APPEND.read_text(encoding="utf-8")
    live_text = LIVE_EVIDENCE.read_text(encoding="utf-8")
    research_state_text = RESEARCH_STATE.read_text(encoding="utf-8")
    human_view_text = HUMAN_VIEW.read_text(encoding="utf-8")
    worker_text = WORKER_RUNTIME.read_text(encoding="utf-8")
    cli_text = CLI.read_text(encoding="utf-8")
    legacy_name = "legacy" + "_core"
    assert not (REPO_ROOT / f"loopx/capabilities/auto_research/{legacy_name}.py").exists()
    assert legacy_name not in evidence_text
    assert legacy_name not in cli_text
    assert f"from .{legacy_name} import" not in rollout_text
    assert f"from .{legacy_name} import" not in live_text
    assert f"from .{legacy_name} import" not in worker_text
    assert f"from .{legacy_name} import" not in cli_text
    assert "from .evidence_packet import (" in worker_text
    assert "from .quickstart_seed import (" in worker_text
    assert "from .research_state import (" in worker_text
    assert "RESEARCH_HYPOTHESIS_SCHEMA_VERSION" in worker_text
    assert "load_auto_research_evidence_packet_inputs" in worker_text
    assert "from .evidence_packet import load_auto_research_evidence_packet_inputs" in cli_text
    assert "from .quickstart_seed import (" in cli_text
    assert "from .research_state import (" in cli_text
    assert "build_live_auto_research_projection" in cli_text
    assert "build_auto_research_projection" in research_state_text
    assert "load_auto_research_fixture" in research_state_text
    assert "render_auto_research_markdown" in human_view_text
    for removed_surface in (
        "build_auto_research_board_projection",
        "build_auto_research_demo_acceptance_packet",
        "build_research_artifact_packet",
        "build_research_showcase_projection",
        "AUTO_RESEARCH_BOARD_SCHEMA_VERSION",
        "AUTO_RESEARCH_DEMO_ACCEPTANCE_PACKET_SCHEMA_VERSION",
        "RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION",
        "AUTO_RESEARCH_PUBLIC_CLAIM_BOUNDARY_SCHEMA_VERSION",
    ):
        assert removed_surface not in research_state_text, removed_surface
        assert removed_surface not in human_view_text, removed_surface
        assert removed_surface not in cli_text, removed_surface


def main() -> None:
    assert_kernel_boundary()
    assert_evidence_packet_boundary()

    candidates = [
        lightweight_hypothesis(
            hypothesis_id="hyp_full_sort",
            todo_id="todo_auto_research_minimal_001",
            claimed_by="research-curator",
            text="Keep full sorting as the baseline candidate.",
            candidate_key="full_sort",
        ),
        lightweight_hypothesis(
            hypothesis_id="hyp_partial_selection",
            todo_id="todo_auto_research_minimal_002",
            claimed_by="evidence-runner",
            text="Use exact partial selection before full sorting.",
            candidate_key="partial_selection",
        ),
    ]

    def evaluate(hypothesis: dict[str, Any], split: str) -> dict[str, Any]:
        metrics = {
            ("full_sort", "dev"): 1.0,
            ("partial_selection", "dev"): 4.0,
            ("partial_selection", "holdout"): 4.5,
        }
        return {
            "metric": metrics[(hypothesis["candidate_key"], split)],
            "exact": True,
            "protected_scope_clean": True,
            "strategy": hypothesis["candidate_key"],
            "artifact_refs": [f"public_metric:{split}:{hypothesis['candidate_key']}"],
            "result_source": "injected_metric_evaluator",
        }

    payload = run_lightweight_auto_research(
        goal_id="loopx-auto-research-minimal-smoke",
        hypotheses=candidates,
        evaluate=evaluate,
        baseline=1.0,
        direction="maximize",
        max_dev_rounds=2,
    )
    assert_positive_result(payload)

    help_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "markdown",
            "auto-research",
            "--help",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert "lite-e2e" not in help_result.stdout
    assert " board " not in help_result.stdout
    assert " acceptance " not in help_result.stdout


if __name__ == "__main__":
    main()
