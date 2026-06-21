#!/usr/bin/env python3
"""Smoke-test the interrupt comparison projection decision boundary."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"
DECISION_DOC = TOPIC_DIR / "mini-control-plane-interrupt-projection-decision-v0.md"
STATUS = REPO_ROOT / "loopx" / "status.py"
REVIEW_PACKET = REPO_ROOT / "loopx" / "review_packet.py"
HOT_PATH_SMOKE = REPO_ROOT / "examples" / "hot-path-interface-budget-smoke.py"

SUMMARY_SCHEMA = "benchmark_interrupt_comparison_summary_v0"
DECISION_DOC_NAME = "mini-control-plane-interrupt-projection-decision-v0.md"
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
    readme = README.read_text(encoding="utf-8")
    status_source = STATUS.read_text(encoding="utf-8")
    review_source = REVIEW_PACKET.read_text(encoding="utf-8")
    hot_path_smoke = HOT_PATH_SMOKE.read_text(encoding="utf-8")

    required_doc_text = [
        SUMMARY_SCHEMA,
        "remains research-only for now",
        "Do not project it into LoopX status or review-packet hot paths",
        "Projection Gate",
        "official_task_score_delta",
        "control_plane_score_delta",
        "restart_resume_evidence",
        "failure_attribution",
        "claim_boundary",
        "No real benchmark runner",
    ]
    missing = [item for item in required_doc_text if item not in doc]
    assert not missing, missing

    assert DECISION_DOC_NAME in readme, DECISION_DOC_NAME
    assert SUMMARY_SCHEMA not in status_source, "status hot path should not project this summary yet"
    assert SUMMARY_SCHEMA not in review_source, "review-packet hot path should not project this summary yet"
    assert SUMMARY_SCHEMA not in hot_path_smoke, "hot-path interface budget should not include this summary yet"

    for text in (doc, readme):
        assert_no_forbidden_text(text)

    print("mini-control-plane-interrupt-projection-decision-smoke ok projection=research_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
