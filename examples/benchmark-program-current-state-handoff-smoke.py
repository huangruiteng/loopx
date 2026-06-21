#!/usr/bin/env python3
"""Smoke-test the benchmark program current-state handoff boundary."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
HANDOFF = TOPIC_DIR / "benchmark-program-current-state-handoff-v0.md"
README = TOPIC_DIR / "README.md"
STATUS = REPO_ROOT / "loopx" / "status.py"
REVIEW_PACKET = REPO_ROOT / "loopx" / "review_packet.py"
HOT_PATH_SMOKE = REPO_ROOT / "examples" / "hot-path-interface-budget-smoke.py"

HANDOFF_SCHEMA = "benchmark_program_current_state_handoff_v0"
HANDOFF_DOC_NAME = "benchmark-program-current-state-handoff-v0.md"
REQUIRED_OWNER_DOCS = [
    "paper-runner-dossier.md",
    "terminal-bench-probe-v0.md",
    "terminal-bench-official-pilot-readiness-v0.md",
    "benchmark-run-v0-ingest.md",
    "passive-baseline-protocol-v0.md",
    "benchmark-result-control-plane-score-v0.md",
    "benchmark-report-chain-map-v0.md",
    "benchmark-history-reconstructability-v0.md",
    "benchmark-restart-actionability-v0.md",
    "mini-control-plane-interrupt-projection-decision-v0.md",
    "terminal-bench-no-submit-approval-packet-projection-decision-v0.md",
    "benchmark-restart-actionability-projection-decision-v0.md",
    "terminal-bench-no-submit-approval-packet-v0.md",
]
FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPEN" + "AI" + "_API" + "_KEY",
    "ANTH" + "ROPIC" + "_API" + "_KEY",
    "DAYTONA" + "_API" + "_KEY",
    "lark" + "office",
    "fei" + "shu.cn",
    "raw" + "_thread",
    "session" + "_history",
]


def assert_no_forbidden_text(text: str) -> None:
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def main() -> int:
    doc = HANDOFF.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    status_source = STATUS.read_text(encoding="utf-8")
    review_source = REVIEW_PACKET.read_text(encoding="utf-8")
    hot_path_source = HOT_PATH_SMOKE.read_text(encoding="utf-8")

    required_doc_text = [
        "Current State",
        "Fresh Worker Read Order",
        "Allowed Next Transitions",
        "ask_no_submit_setup_approval",
        "passively_ingest_existing_official_output",
        "quiet_stop",
        "Projection Policy",
        "research/docs-only",
        "No official run has been executed or claimed",
        "No Terminal-Bench or Harbor runner execution",
    ]
    missing = [item for item in required_doc_text if item not in doc]
    assert not missing, missing

    missing_owner_docs = [name for name in REQUIRED_OWNER_DOCS if name not in doc]
    assert not missing_owner_docs, missing_owner_docs
    for name in REQUIRED_OWNER_DOCS:
        assert (TOPIC_DIR / name).exists(), name

    assert HANDOFF_DOC_NAME in readme, HANDOFF_DOC_NAME
    assert HANDOFF_SCHEMA not in status_source, "status hot path should not project this handoff"
    assert HANDOFF_SCHEMA not in review_source, "review-packet hot path should not project this handoff"
    assert HANDOFF_SCHEMA not in hot_path_source, "hot-path budget should not include this handoff"

    for text in (doc, readme):
        assert_no_forbidden_text(text)

    print(
        "benchmark-program-current-state-handoff-smoke ok "
        f"owner_docs={len(REQUIRED_OWNER_DOCS)} transitions=3 projection=docs_only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
