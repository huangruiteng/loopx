#!/usr/bin/env python3
"""Smoke-test KNN benchmark contract normalization into auto-research evidence."""

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

from loopx.capabilities.auto_research.knn_demo_workspace import (  # noqa: E402
    materialize_knn_demo_workspace,
)


HYPOTHESIS_ID = "HYP-KNN-TOPK-HEAP"
TODO_ID = "todo_knn_topk_heap"
AGENT_ID = "research-executor"
GOAL_ID = "loopx-auto-research-knn-smoke"
MECHANISM_FAMILY = "topk_heap_exact"
HYPOTHESIS_TEXT = "Use exact heap top-k selection instead of full sorting."


TOPK_SOLUTION = '''from __future__ import annotations

from heapq import nsmallest


def _squared_distance(left, right) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def solve(problem):
    database = problem["database"]
    k = int(problem["k"])
    output = []
    for query in problem["queries"]:
        nearest = nsmallest(
            k,
            ((_squared_distance(row, query), index) for index, row in enumerate(database)),
        )
        output.append([index for _distance, index in nearest])
    return output
'''


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


def run_eval(workspace: Path, split: str, output: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["bash", "eval.sh", split],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def run_evidence(contract: Path, dev: Path, holdout: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "auto-research",
            "evidence",
            "--contract",
            str(contract),
            "--eval-result",
            str(dev),
            "--eval-result",
            str(holdout),
            "--hypothesis-id",
            HYPOTHESIS_ID,
            "--todo-id",
            TODO_ID,
            "--agent-id",
            AGENT_ID,
            "--claimed-by",
            AGENT_ID,
            "--mechanism-family",
            MECHANISM_FAMILY,
            "--hypothesis",
            HYPOTHESIS_TEXT,
            "--grounding-ref",
            "contract:research_contract.public.json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"auto-research evidence failed rc={result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "knn-workspace"
        materialize_knn_demo_workspace(workspace, goal_id=GOAL_ID)
        (workspace / "solution.py").write_text(TOPK_SOLUTION, encoding="utf-8")

        artifacts = Path(temp_dir) / "artifacts"
        artifacts.mkdir()
        dev = artifacts / "dev.public.json"
        holdout = artifacts / "holdout.public.json"
        dev_payload = run_eval(workspace, "dev", dev)
        holdout_payload = run_eval(workspace, "test", holdout)
        assert dev_payload["score"] > dev_payload["baseline_score"], dev_payload
        assert holdout_payload["score"] > holdout_payload["baseline_score"], holdout_payload

        packet = run_evidence(workspace / "research_contract.public.json", dev, holdout)
        assert packet["ok"] is True, packet
        assert packet["schema_version"] == "auto_research_evidence_packet_v0", packet
        assert packet["research_contract"]["schema_version"] == "research_contract_v0", packet
        assert packet["research_contract"]["goal_id"] == GOAL_ID, packet
        assert packet["summary"]["goal_id"] == GOAL_ID, packet
        assert packet["hypothesis"]["status"] == "supported", packet
        assert packet["summary"]["splits"] == ["dev", "holdout"], packet
        assert packet["summary"]["protected_scope_clean"] is True, packet
        assert {event["primary_metric_status"] for event in packet["evidence_events"]} == {
            "improved"
        }, packet
        assert all(event["metric"]["value"] > event["baseline_metric"] for event in packet["evidence_events"]), packet
        assert any(
            "command:bash-eval.sh-test" in event["artifact_refs"]
            for event in packet["evidence_events"]
        ), packet
        assert_public_safe(packet)

        (workspace / "task.py").write_text("# protected change\n", encoding="utf-8")
        dirty_packet = run_evidence(workspace / "research_contract.public.json", dev, holdout)
        assert dirty_packet["hypothesis"]["status"] == "contradicted", dirty_packet
        assert dirty_packet["summary"]["protected_scope_clean"] is False, dirty_packet
        assert dirty_packet["summary"]["negative_evidence_count"] == 2, dirty_packet
        assert_public_safe(dirty_packet)

    print("auto-research-knn-evidence-normalization-smoke ok")


if __name__ == "__main__":
    main()
