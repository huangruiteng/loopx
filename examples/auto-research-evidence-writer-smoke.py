#!/usr/bin/env python3
"""Smoke-test public-safe auto-research evidence packet generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
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


def run_json(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def eval_result(split: str) -> dict[str, Any]:
    result = run_json(
        [
            str(EVAL),
            "--solution",
            str(CANDIDATE),
            "--split",
            split,
        ]
    )
    return json.loads(result.stdout)


def run_evidence_cli(paths: list[Path], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    args = [
        "-m",
        "loopx.cli",
        "--format",
        "json",
        "auto-research",
        "evidence",
        "--contract",
        str(CONTRACT),
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
        "codex/auto-research-evidence-writer-smoke",
    ]
    for path in paths:
        args.extend(["--eval-result", str(path)])
    return run_json(args, check=check)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        dev = temp / "dev.json"
        holdout = temp / "holdout.json"
        write_json(dev, eval_result("dev"))
        write_json(holdout, eval_result("holdout"))

        result = run_evidence_cli([dev, holdout])
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["schema_version"] == "auto_research_evidence_packet_v0", payload
        assert payload["hypothesis"]["schema_version"] == "research_hypothesis_v0", payload
        assert payload["hypothesis"]["status"] == "supported", payload
        assert payload["summary"]["splits"] == ["dev", "holdout"], payload
        assert payload["summary"]["negative_evidence_count"] == 0, payload
        assert payload["summary"]["needs_retry_count"] == 0, payload
        assert payload["summary"]["protected_scope_clean"] is True, payload
        assert len(payload["evidence_events"]) == 2, payload
        assert {event["schema_version"] for event in payload["evidence_events"]} == {
            "research_evidence_event_v0"
        }, payload
        assert {event["split"] for event in payload["evidence_events"]} == {"dev", "holdout"}, payload
        assert all(event["raw_logs_recorded"] is False for event in payload["evidence_events"]), payload
        assert all(event["private_artifacts_recorded"] is False for event in payload["evidence_events"]), payload
        assert any(
            "branch:codex/auto-research-evidence-writer-smoke" in event["artifact_refs"]
            for event in payload["evidence_events"]
        ), payload
        assert_public_safe(payload)

        retry = temp / "retry.json"
        write_json(
            retry,
            {
                "schema_version": "auto_research_knn_eval_result_v0",
                "split": "dev",
                "metric": {
                    "name": "deterministic_speedup",
                    "direction": "maximize",
                    "value": None,
                    "baseline": 1.0,
                },
                "eval_status": "failed_to_run",
                "primary_metric_status": "inconclusive",
                "artifact_refs": ["knn_pack:dev:retry"],
                "protected_scope_clean": True,
                "no_upload": True,
            },
        )
        retry_payload = json.loads(run_evidence_cli([retry]).stdout)
        assert retry_payload["hypothesis"]["status"] == "needs_retry", retry_payload
        assert retry_payload["summary"]["needs_retry_count"] == 1, retry_payload
        assert retry_payload["summary"]["negative_evidence_count"] == 0, retry_payload
        assert retry_payload["evidence_events"][0]["eval_status"] == "failed_to_run", retry_payload
        assert_public_safe(retry_payload)

        dirty = temp / "dirty.json"
        dirty_payload = eval_result("dev")
        dirty_payload["protected_scope_clean"] = False
        write_json(dirty, dirty_payload)
        contradicted = json.loads(run_evidence_cli([dirty]).stdout)
        assert contradicted["hypothesis"]["status"] == "contradicted", contradicted
        assert contradicted["summary"]["negative_evidence_count"] == 1, contradicted
        assert contradicted["summary"]["protected_scope_clean"] is False, contradicted
        assert_public_safe(contradicted)

        bad = temp / "bad.json"
        bad_payload = eval_result("dev")
        bad_payload["artifact_refs"] = ["/" + "Users/example/raw.log"]
        write_json(bad, bad_payload)
        blocked = run_evidence_cli([bad], check=False)
        blocked_payload = json.loads(blocked.stdout)
        assert blocked.returncode == 1, blocked_payload
        assert blocked_payload["ok"] is False, blocked_payload
        assert "public alias" in blocked_payload["error"], blocked_payload

    print("auto-research-evidence-writer-smoke ok")


if __name__ == "__main__":
    main()
