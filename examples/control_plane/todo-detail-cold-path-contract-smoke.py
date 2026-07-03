#!/usr/bin/env python3
"""Smoke-test the todo detail cold-path contract boundary."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = REPO_ROOT / "docs" / "reference" / "protocols" / "todo-detail-cold-path-v0.md"
PROTOCOLS_README = REPO_ROOT / "docs" / "reference" / "protocols" / "README.md"
STATUS_CONTRACT = REPO_ROOT / "docs" / "status-data-contract.md"
STATUS_SOURCE = REPO_ROOT / "loopx" / "status.py"
QUOTA_SOURCE = REPO_ROOT / "loopx" / "quota.py"
HOT_PATH_SMOKE = REPO_ROOT / "examples" / "control_plane" / "hot-path-interface-budget-smoke.py"

DETAIL_SCHEMA = "todo_detail_cold_path_v0"
REF_SCHEMA = "todo_detail_ref_v0"
PROTOCOL_DOC_NAME = "todo-detail-cold-path-v0.md"
FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPEN" + "AI" + "_API" + "_KEY",
    "ANTH" + "ROPIC" + "_API" + "_KEY",
    "raw" + "_thread",
    "session" + "_history",
    "verifier" + "_output_tail",
]


def assert_no_forbidden_text(text: str) -> None:
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def main() -> int:
    protocol = PROTOCOL.read_text(encoding="utf-8")
    protocols_readme = PROTOCOLS_README.read_text(encoding="utf-8")
    status_contract = STATUS_CONTRACT.read_text(encoding="utf-8")
    status_source = STATUS_SOURCE.read_text(encoding="utf-8")
    quota_source = QUOTA_SOURCE.read_text(encoding="utf-8")
    hot_path_smoke = HOT_PATH_SMOKE.read_text(encoding="utf-8")

    required_protocol_text = [
        DETAIL_SCHEMA,
        REF_SCHEMA,
        "Cold-Path Shape",
        "Paging Rules",
        "truth_contract.projection_is_writable=false",
        "truth_contract.write_api=false",
        "active_goal_state_and_event_ledger",
        "Raw task text, transcripts",
        "consumers can safely ignore",
    ]
    missing = [item for item in required_protocol_text if item not in protocol]
    assert not missing, missing

    assert PROTOCOL_DOC_NAME in protocols_readme, PROTOCOL_DOC_NAME
    assert PROTOCOL_DOC_NAME in status_contract, PROTOCOL_DOC_NAME
    assert REF_SCHEMA in status_contract, REF_SCHEMA
    assert DETAIL_SCHEMA in status_contract, DETAIL_SCHEMA
    status_excerpt_start = status_contract.index(PROTOCOL_DOC_NAME)
    status_excerpt = status_contract[status_excerpt_start : status_excerpt_start + 700]

    assert DETAIL_SCHEMA not in status_source, "status hot path should not inline todo detail yet"
    assert DETAIL_SCHEMA not in quota_source, "quota hot path should not inline todo detail yet"
    assert DETAIL_SCHEMA not in hot_path_smoke, "hot-path budget smoke should not include todo detail"

    for text in (protocol, protocols_readme, status_excerpt):
        assert_no_forbidden_text(text)

    print("todo-detail-cold-path-contract-smoke ok projection=docs_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
