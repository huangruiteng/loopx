#!/usr/bin/env python3
"""Smoke-test the public openviking_session_memory_adapter_v0 fixture."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "examples" / "fixtures" / "openviking-session-memory-adapter.public.json"
CONTRACT_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "openviking-session-memory-adapter-v0.md"
PROTOCOL_INDEX_PATH = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
DOCS_INDEX_PATH = REPO_ROOT / "docs" / "README.md"
STATUS_CONTRACT_PATH = REPO_ROOT / "docs" / "status-data-contract.md"
SESSION_ADAPTER_PATH = REPO_ROOT / "docs" / "session-runtime-control-plane-adapter.md"

REQUIRED_TRUTH_SOURCES = {
    "loopx_goal_state",
    "session_runtime_projection",
    "public_issue_metadata",
    "memory_system_refs",
}
REQUIRED_GATES = {
    "live_openviking_retrieval",
    "memory_writeback",
    "issue_body_read",
    "comment_body_read",
    "raw_tool_output_ingest",
}
REQUIRED_FUTURE_GATES = REQUIRED_GATES | {"external_issue_comment_or_pr_publish"}
ALLOWED_SCORE_BUCKETS = {"high", "medium", "low", "unknown"}
ALLOWED_SOURCE_KINDS = {
    "prior_issue",
    "session_outcome",
    "operator_note",
    "validation_summary",
    "unknown",
}
PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r'https?://[^\s"]*(?:corp-only|restricted-host)[^\s"]*'),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_public_safe(text: str, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"{label} matched private pattern {pattern.pattern!r}")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} missing {needle!r}")


def main() -> int:
    fixture_text = read(FIXTURE_PATH)
    contract = read(CONTRACT_PATH)
    protocol_index = read(PROTOCOL_INDEX_PATH)
    docs_index = read(DOCS_INDEX_PATH)
    status_contract = read(STATUS_CONTRACT_PATH)
    session_adapter = read(SESSION_ADAPTER_PATH)

    for label, text in {
        "fixture": fixture_text,
        "contract": contract,
        "protocol index": protocol_index,
        "docs index": docs_index,
        "status contract": status_contract,
        "session adapter": session_adapter,
    }.items():
        assert_public_safe(text, label)

    for needle in [
        "openviking_session_memory_adapter_v0",
        "session_runtime_loopx_projection_v0",
        "live OpenViking retrieval",
        "memory writeback",
        "raw trajectories",
        "comment bodies",
        "tool outputs",
    ]:
        assert_contains(contract, needle, "contract")
    assert_contains(protocol_index, "openviking_session_memory_adapter_v0", "protocol index")
    assert_contains(docs_index, "OpenViking session memory adapter v0", "docs index")
    assert_contains(status_contract, "openviking_session_memory_adapter_v0", "status contract")
    assert_contains(session_adapter, "openviking_session_memory_adapter_v0", "session adapter")

    payload = json.loads(fixture_text)
    item = payload["attention_queue"]["items"][0]
    adapter = item["openviking_session_memory_adapter"]

    assert adapter["schema_version"] == "openviking_session_memory_adapter_v0", adapter
    assert adapter["mode"] == "read_only_projection", adapter
    assert adapter["specializes"] == "session_runtime_loopx_projection_v0", adapter
    assert adapter["goal_id"] == item["goal_id"], adapter

    issue = adapter["issue_projection"]
    assert issue["provider"] == "github", issue
    assert issue["repo"] == "OpenViking/Viking", issue
    assert isinstance(issue["issue_number"], int), issue
    assert issue["issue_body_copied"] is False, issue
    assert issue["comment_bodies_copied"] is False, issue
    assert issue["provider_payload_copied"] is False, issue

    session = adapter["session_projection"]
    assert session["runtime_id"], session
    assert session["session_refs"], session
    assert session["linked_todo_ids"], session
    assert session["raw_trajectory_copied"] is False, session
    assert session["raw_transcripts_copied"] is False, session
    assert session["raw_tool_outputs_copied"] is False, session

    memory = adapter["memory_projection"]
    assert memory["namespace"] == "openviking_issue_fix_public_preview", memory
    assert memory["retrieval_mode"] in {"preview_only", "disabled", "future_gated"}, memory
    assert memory["live_retrieval_performed"] is False, memory
    assert memory["writeback_performed"] is False, memory
    assert isinstance(memory["top_k_preview"], int) and memory["top_k_preview"] > 0, memory
    candidates = memory["candidate_refs"]
    assert isinstance(candidates, list) and candidates, memory
    for candidate in candidates:
        assert candidate["memory_ref_id"].startswith("mem_"), candidate
        assert candidate["source_kind"] in ALLOWED_SOURCE_KINDS, candidate
        assert candidate["score_bucket"] in ALLOWED_SCORE_BUCKETS, candidate
        assert isinstance(candidate["summary"], str) and candidate["summary"], candidate
        assert candidate["raw_memory_copied"] is False, candidate

    retrieval_gates = {gate["capability"]: gate for gate in adapter["retrieval_gates"]}
    assert REQUIRED_GATES <= set(retrieval_gates), retrieval_gates
    for gate in retrieval_gates.values():
        assert gate["state"] in {"future_gated", "blocked_without_authority", "approved"}, gate
        assert isinstance(gate["required_authority"], str) and gate["required_authority"], gate
        assert isinstance(gate["blocks"], str) and gate["blocks"], gate

    assert REQUIRED_FUTURE_GATES <= set(adapter["future_gates"]), adapter["future_gates"]

    status = adapter["status_projection"]
    assert status["waiting_on"] == "agent", status
    assert status["user_action_required"] is False, status
    assert status["agent_can_continue"] is True, status
    assert status["memory_state"] == "preview_only", status

    evidence = adapter["evidence_projection"]
    assert evidence["source_refs"], evidence
    assert evidence["validation_refs"], evidence
    for flag in [
        "raw_trajectories_copied",
        "comment_bodies_copied",
        "raw_tool_outputs_copied",
        "credentials_copied",
        "private_paths_copied",
    ]:
        assert evidence[flag] is False, (flag, evidence)

    truth = adapter["truth_contract"]
    assert set(truth["source_of_truth"]) == REQUIRED_TRUTH_SOURCES, truth
    assert truth["adapter_is_writable"] is False, truth
    assert truth["live_retrieval_allowed"] is False, truth
    assert truth["memory_writeback_allowed"] is False, truth
    assert truth["issue_body_read_allowed"] is False, truth
    assert truth["comment_body_read_allowed"] is False, truth
    assert truth["tool_output_ingest_allowed"] is False, truth

    forbidden_values = [
        "full transcript body",
        "raw trajectory line",
        "comment body text",
        "tool output text",
        "credential-value",
        "secret-value",
    ]
    leaked = [value for value in forbidden_values if value in fixture_text]
    assert not leaked, leaked

    print("openviking-session-memory-adapter-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
