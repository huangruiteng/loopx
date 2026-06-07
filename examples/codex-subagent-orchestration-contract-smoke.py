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
    "The main controller owns the shared-control-plane handoff and the final",
    "child reports evidence only; parent writes and spends",
    "control_plane_handoff_version",
    "A child may produce evidence, a validation result, or a blocker",
)

FORBIDDEN_PHRASES = (
    "/Users/bytedance/",
    "lark" + "office.com",
    "~/.codex/sessions",
    "raw_thread",
    "session_history",
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
