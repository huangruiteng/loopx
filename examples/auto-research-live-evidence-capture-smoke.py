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
GOAL_ID = "loopx-auto-research-knn"
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


def run_eval(pack_dir: Path, split: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            str(pack_dir / "protected_eval.py"),
            "--solution",
            str(pack_dir / "solution_candidate.py"),
            "--split",
            split,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    (pack_dir / f"{split}-result.public.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


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

        quickstart = run_cli(
            [
                "auto-research",
                "quickstart",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--output-dir",
                "auto_research_knn_pack",
                "--execute",
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
        )
        pack_dir = workspace / json.loads(quickstart.stdout)["pack_dir"]
        dev = run_eval(pack_dir, "dev")
        holdout = run_eval(pack_dir, "holdout")
        assert dev["metric"]["value"] == 4.0, dev
        assert holdout["metric"]["value"] == 4.5, holdout

        evidence = run_cli(
            [
                "auto-research",
                "evidence",
                "--contract",
                str(pack_dir / "research_contract.json"),
                "--eval-result",
                str(pack_dir / "dev-result.public.json"),
                "--eval-result",
                str(pack_dir / "holdout-result.public.json"),
                "--hypothesis-id",
                "hyp_live_lane_partial_selection",
                "--todo-id",
                "todo_live_lane_partial_selection",
                "--agent-id",
                AGENT_ID,
                "--claimed-by",
                AGENT_ID,
                "--mechanism-family",
                "partial_selection",
                "--hypothesis",
                "Use exact partial selection to avoid full distance sorting.",
                "--grounding-ref",
                "visible-lane:public-demo",
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
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
        )
        append_payload = json.loads(append.stdout)
        append_path = workspace / "append-result.public.json"
        append_path.write_text(json.dumps(append_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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

        claimed = run_cli(
            [
                "auto-research",
                "demo-e2e",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                AGENT_ID,
                "--execute",
                "--live-evidence",
                str(live_path),
            ],
            registry=registry,
            runtime_root=runtime_root,
            cwd=workspace,
        )
        claimed_payload = json.loads(claimed.stdout)
        live = claimed_payload["live_codex_e2e"]
        assert live["executed"] is True, claimed_payload
        assert live["claim_allowed"] is True, claimed_payload
        assert live["evidence_source"] == "live_codex_lane_output", claimed_payload
        assert live["evidence_event_count"] == 2, claimed_payload
        assert live["dev_metric"] == 4.0, claimed_payload
        assert live["holdout_metric"] == 4.5, claimed_payload
        assert_public_safe(claimed_payload)

    print("auto-research-live-evidence-capture-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
