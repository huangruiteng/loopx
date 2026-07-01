#!/usr/bin/env python3
"""Smoke-test appending auto-research evidence packets into rollout events."""

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

from loopx.rollout_event_log import load_rollout_events, rollout_event_log_path  # noqa: E402


PACK = REPO_ROOT / "examples/auto_research_knn_pack"
EVAL = PACK / "protected_eval.py"
CONTRACT = PACK / "research_contract.json"
CANDIDATE = PACK / "solution_candidate.py"


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
            "codex/auto-research-rollout-append-smoke",
        ]
    )


def append_packet(
    registry: Path,
    packet: Path,
    *,
    dry_run: bool = False,
    output: Path | None = None,
) -> dict[str, Any]:
    args = [
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
    if dry_run:
        args.append("--dry-run")
    if output is not None:
        args.extend(["--output", str(output)])
    return run_json(args)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        runtime_root = temp / "runtime"
        registry = temp / "registry.json"
        registry.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "common_runtime_root": str(runtime_root),
                    "goals": [
                        {
                            "id": "loopx-meta",
                            "domain": "auto_research_smoke",
                            "status": "active",
                            "repo": str(REPO_ROOT),
                            "state_file": "ACTIVE_GOAL_STATE.md",
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

        dry = append_packet(registry, packet_path, dry_run=True)
        assert dry["schema_version"] == "auto_research_rollout_append_v0", dry
        assert dry["dry_run"] is True, dry
        assert dry["event_count"] == 3, dry
        assert dry["would_append_count"] == 3, dry
        assert dry["appended_count"] == 0, dry
        assert dry["counts_by_kind"] == {
            "research_evidence": 2,
            "research_hypothesis": 1,
        }, dry
        assert_public_safe(dry)

        append_output = temp / "append-result.public.json"
        first = append_packet(registry, packet_path, output=append_output)
        assert first["dry_run"] is False, first
        assert first["event_count"] == 3, first
        assert first["appended_count"] == 3, first
        assert first["skipped_existing_count"] == 0, first
        assert append_output.is_file(), first
        assert json.loads(append_output.read_text(encoding="utf-8")) == first, first
        assert_public_safe(first)

        second = append_packet(registry, packet_path)
        assert second["appended_count"] == 0, second
        assert second["would_append_count"] == 0, second
        assert second["skipped_existing_count"] == 3, second
        assert_public_safe(second)

        events = load_rollout_events(rollout_event_log_path(runtime_root, first["goal_id"]))
        assert len(events) == 3, events
        assert {event["event_kind"] for event in events} == {
            "research_hypothesis",
            "research_evidence",
        }, events
        hypothesis = [event for event in events if event["event_kind"] == "research_hypothesis"][0]
        evidence = [event for event in events if event["event_kind"] == "research_evidence"]
        assert hypothesis["classification"] == "research_hypothesis_v0", hypothesis
        assert hypothesis["details"]["evidence_event_count"] == 2, hypothesis
        assert {event["classification"] for event in evidence} == {
            "research_evidence_event_v0"
        }, evidence
        assert {event["details"]["split"] for event in evidence} == {"dev", "holdout"}, evidence
        assert all(event["boundary"]["raw_logs_recorded"] is False for event in events), events
        assert all(event["boundary"]["absolute_paths_recorded"] is False for event in events), events
        assert_public_safe(events)

    print("auto-research-rollout-append-smoke ok")


if __name__ == "__main__":
    main()
