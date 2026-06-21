#!/usr/bin/env python3
"""Smoke-test the no-submit approval packet projection decision boundary."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
DECISION_DOC = TOPIC_DIR / "terminal-bench-no-submit-approval-packet-projection-decision-v0.md"
PACKET_DOC = TOPIC_DIR / "terminal-bench-no-submit-approval-packet-v0.md"
STATUS = REPO_ROOT / "loopx" / "status.py"
REVIEW_PACKET = REPO_ROOT / "loopx" / "review_packet.py"
HOT_PATH_SMOKE = REPO_ROOT / "examples" / "hot-path-interface-budget-smoke.py"

PACKET_SCHEMA = "terminal_bench_no_submit_approval_packet_v0"
DECISION_DOC_NAME = "terminal-bench-no-submit-approval-packet-projection-decision-v0.md"
FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    "OPEN" + "AI" + "_API" + "_KEY",
    "ANTH" + "ROPIC" + "_API" + "_KEY",
    "lark" + "office",
    "fei" + "shu.cn",
    "raw" + "_thread",
    "session" + "_history",
]


def assert_no_forbidden_text(text: str) -> None:
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked


def main() -> int:
    doc = DECISION_DOC.read_text(encoding="utf-8")
    packet_doc = PACKET_DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    status_source = STATUS.read_text(encoding="utf-8")
    review_source = REVIEW_PACKET.read_text(encoding="utf-8")
    hot_path_smoke = HOT_PATH_SMOKE.read_text(encoding="utf-8")

    required_doc_text = [
        PACKET_SCHEMA,
        "remains research/docs-only",
        "Do not project it into LoopX status, review-packet, or project-asset",
        "Projection Gate",
        "approval_state",
        "execution_authorized",
        "submit_eligible",
        "real_run",
        "candidate_command_count",
        "forbidden_surface_count",
        "expected_public_artifact_count",
        "next_required_operator_action",
        "No Terminal-Bench or Harbor runner execution",
    ]
    missing = [item for item in required_doc_text if item not in doc]
    assert not missing, missing

    assert PACKET_SCHEMA in packet_doc, "packet doc should still own the schema contract"
    assert DECISION_DOC_NAME in readme, DECISION_DOC_NAME
    assert PACKET_SCHEMA not in status_source, "status hot path should not project this packet yet"
    assert PACKET_SCHEMA not in review_source, "review-packet hot path should not project this packet yet"
    assert PACKET_SCHEMA not in hot_path_smoke, "hot-path interface budget should not include this packet yet"

    for text in (doc, readme):
        assert_no_forbidden_text(text)

    print("terminal-bench-no-submit-approval-packet-projection-decision-smoke ok projection=docs_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
