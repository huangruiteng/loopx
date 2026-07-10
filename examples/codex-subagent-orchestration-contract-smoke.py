#!/usr/bin/env python3
"""Smoke-test the Codex sub-agent shared-control-plane contract."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "codex-subagent-orchestration.md"

REQUIRED_PHRASES = (
    "shared control plane",
    "subagent_control_plane_handoff_v0",
    "`parent_goal_id`",
    "`authority_artifact`",
    "`latest_state_ref`",
    "`quota_gate_snapshot`",
    "`evidence_boundary`",
    "`writeback_spend_contract`",
    "`child_decision`",
    "`continue`, `wait`, or `reuse_existing_evidence`",
    "The temporary task coordinator may aggregate child evidence",
    "child reports evidence only; parent writes and spends",
    "control_plane_handoff_version",
    "It does not own durable goal authority",
    "one pending lease for `(goal_id, todo_id)`",
    "`goal_id` is the shared control-plane lane",
    "`todo_id` is the work item being claimed",
    '"agent_model": "peer_v1"',
    "independent worktrees",
    "explicit `review_handoff`",
)

FORBIDDEN_PHRASES = (
    "PRIVATE_HOME/",
    "lark" + "office.com",
    "~/.codex/sessions",
    "raw_thread",
    "session_history",
    "coordination.primary_agent",
    "primary-agent review todo",
    "side agents",
)


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    compact = " ".join(text.split())
    for phrase in REQUIRED_PHRASES:
        assert phrase in compact, phrase
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, phrase
    assert text.count("subagent_control_plane_handoff_v0") >= 2, text
    assert text.count("## ") >= 7, text
    print("codex-subagent-orchestration-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
