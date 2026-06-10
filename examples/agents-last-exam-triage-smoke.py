#!/usr/bin/env python3
"""Smoke-test the Agents' Last Exam benchmark triage note."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "agents-last-exam-triage-v0.md"
README = TOPIC_DIR / "README.md"
ROADMAP = TOPIC_DIR / "roadmap.md"

SCHEMA = "agents_last_exam_triage_v0"
BENCHMARK_ID = "agents-last-exam"
ARXIV_ID = "2606.05405"
XHS_NOTE_ID = "6a29525a0000000022023914"

REQUIRED_DOC_SNIPPETS = [
    "Agents' Last Exam Triage V0",
    "http://xhslink.com/o/1tiETi329bL",
    XHS_NOTE_ID,
    "https://arxiv.org/abs/2606.05405",
    "https://github.com/rdi-berkeley/agents-last-exam",
    "Terminal-Bench",
    "fix-code-vulnerability",
    "python3 examples/agents-last-exam-triage-smoke.py",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "sk-" + "example",
]


def triage_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "source_links": {
            "xiaohongshu_note_id": XHS_NOTE_ID,
            "arxiv_id": ARXIV_ID,
            "github_repo": "rdi-berkeley/agents-last-exam",
        },
        "positioning": {
            "long_horizon": True,
            "economically_valuable_workflows": True,
            "real_os_sandboxes": True,
            "gui_and_cli_surface": True,
            "verifiable_outcomes": True,
        },
        "planning_decision": {
            "add_to_backlog": True,
            "priority": "P1/P2_follow_on",
            "do_not_displace_terminal_bench_first_pair": True,
            "requires_adapter_dossier_before_execution": True,
            "first_current_pair": "terminal-bench@2.0/fix-code-vulnerability",
        },
        "stop_conditions": [
            "do_not_run_cloud_sandbox_or_paid_compute_from_heartbeat",
            "do_not_copy_hidden_references_or_raw_trajectories",
            "do_not_treat_social_summary_as_authoritative_without_primary_sources",
            "do_not_replace_current_terminal_bench_pair_before_result_or_blocker",
        ],
    }


def assert_public_safe(value: Any) -> None:
    text = json.dumps(value, sort_keys=True, ensure_ascii=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 10000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    leaked = [snippet for snippet in FORBIDDEN_TEXT if snippet in text]
    assert not leaked, leaked
    assert "agents-last-exam-triage-v0.md" in readme, readme
    assert "Agents' Last Exam" in roadmap, roadmap


def assert_triage_payload(payload: dict[str, Any]) -> None:
    assert payload["schema_version"] == SCHEMA, payload
    assert payload["benchmark_id"] == BENCHMARK_ID, payload
    assert payload["source_links"]["arxiv_id"] == ARXIV_ID, payload
    assert payload["source_links"]["xiaohongshu_note_id"] == XHS_NOTE_ID, payload
    assert payload["positioning"]["long_horizon"] is True, payload
    decision = payload["planning_decision"]
    assert decision["add_to_backlog"] is True, decision
    assert decision["do_not_displace_terminal_bench_first_pair"] is True, decision
    assert decision["requires_adapter_dossier_before_execution"] is True, decision
    assert decision["first_current_pair"] == "terminal-bench@2.0/fix-code-vulnerability", decision
    assert "do_not_run_cloud_sandbox_or_paid_compute_from_heartbeat" in payload["stop_conditions"], payload
    assert_public_safe(payload)


def main() -> None:
    assert_doc_contract()
    payload = triage_payload()
    assert_triage_payload(payload)
    print(
        "agents-last-exam-triage-smoke ok "
        f"benchmark={payload['benchmark_id']} "
        f"arxiv={payload['source_links']['arxiv_id']} "
        f"xhs={payload['source_links']['xiaohongshu_note_id']}"
    )


if __name__ == "__main__":
    main()
