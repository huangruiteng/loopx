#!/usr/bin/env python3
"""Smoke-test decentralized auto-research fixture projection."""

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

from loopx.auto_research import (  # noqa: E402
    AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION,
    RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION,
    RESEARCH_FRONTIER_SCHEMA_VERSION,
    RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION,
    build_auto_research_projection,
    load_auto_research_fixture,
)


FIXTURE = REPO_ROOT / "examples/fixtures/decentralized-auto-research-knn.public.json"


def assert_no_private_surface(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "s3://",
        "tos://",
        "hdfs://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> None:
    fixture = load_auto_research_fixture(FIXTURE)
    payload = build_auto_research_projection(fixture, agent_id="codex-side-bypass")
    assert payload["ok"], payload
    assert payload["schema_version"] == AUTO_RESEARCH_PROJECTION_SCHEMA_VERSION, payload
    assert payload["frontier"]["schema_version"] == RESEARCH_FRONTIER_SCHEMA_VERSION, payload
    assert payload["evidence_graph"]["schema_version"] == RESEARCH_EVIDENCE_GRAPH_SCHEMA_VERSION, payload
    assert payload["showcase_projection"]["schema_version"] == RESEARCH_SHOWCASE_PROJECTION_SCHEMA_VERSION, payload
    assert payload["frontier"]["agent_id"] == "codex-side-bypass", payload
    assert payload["frontier"]["selected"]["hypothesis_id"] == "hyp_002", payload
    assert payload["frontier"]["selected"]["allowed_action"] == "run_dev_attempt", payload
    assert payload["frontier"]["blocked"][0]["blocked_by"] == "claimed_by:codex-product-capability", payload
    assert payload["evidence_graph"]["holdout_improved"] is True, payload
    assert payload["evidence_graph"]["negative_evidence_count"] == 1, payload
    assert payload["showcase_projection"]["decentralized_pattern"].startswith("todo_linked"), payload
    assert payload["public_boundary"]["raw_logs_recorded"] is False, payload
    assert payload["public_boundary"]["private_artifacts_recorded"] is False, payload
    assert_no_private_surface(payload)

    result = run_cli(
        [
            "--format",
            "json",
            "auto-research",
            "frontier",
            "--fixture",
            str(FIXTURE),
            "--agent-id",
            "codex-side-bypass",
        ]
    )
    cli_payload = json.loads(result.stdout)
    assert cli_payload["ok"], cli_payload
    assert cli_payload["frontier"]["selected"]["todo_id"] == "todo_auto_research_002", cli_payload
    assert_no_private_surface(cli_payload)

    bad_fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bad_fixture["evidence_events"][0]["artifact_refs"] = ["/" + "Users/example/raw.log"]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(bad_fixture, handle)
        bad_path = handle.name
    blocked = run_cli(
        [
            "--format",
            "json",
            "auto-research",
            "frontier",
            "--fixture",
            bad_path,
            "--agent-id",
            "codex-side-bypass",
        ],
        check=False,
    )
    assert blocked.returncode == 1, blocked.stdout
    blocked_payload = json.loads(blocked.stdout)
    assert blocked_payload["ok"] is False, blocked_payload
    assert "public alias" in blocked_payload["error"], blocked_payload

    docs = (REPO_ROOT / "docs/reference/protocols/decentralized-auto-research-state-v0.md").read_text(
        encoding="utf-8"
    )
    assert "decentralized_research_frontier_v0" in docs, docs
    assert "research_showcase_projection_v0" in docs, docs

    print("decentralized-auto-research-frontier-smoke ok")


if __name__ == "__main__":
    main()
