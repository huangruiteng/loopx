#!/usr/bin/env python3
"""Smoke-test the public session-runtime control-plane adapter docs."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "session-runtime-control-plane-adapter.md"
DOCS_INDEX = REPO_ROOT / "docs" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "architecture.md"
CONTRIBUTOR_TASKS = REPO_ROOT / "CONTRIBUTOR_TASKS.md"

def require(text: str, snippets: list[str], *, source: Path) -> None:
    missing = [snippet for snippet in snippets if snippet not in text]
    assert not missing, f"{source}: missing {missing}"


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    contributor_tasks = CONTRIBUTOR_TASKS.read_text(encoding="utf-8")

    require(
        doc,
        [
            "The host session log is the raw fact source.",
            "LoopX run history is a\ncompact control projection.",
            "Phase 1: Read-Only Projection",
            "Phase 2: Controlled Writeback",
            "build_session_runtime_readonly_projection",
            "python3 examples/session-runtime-readonly-projection-smoke.py",
            "quota decision as a scheduler hint, not billing",
            "These metrics are goal-control metrics, not model-quality scores.",
        ],
        source=DOC,
    )
    require(
        docs_index,
        ["Session runtime control-plane adapter"],
        source=DOCS_INDEX,
    )
    require(
        architecture,
        [
            "session-runtime platforms",
            "goal-level control projection",
            "session-runtime-control-plane-adapter.md",
        ],
        source=ARCHITECTURE,
    )
    require(
        contributor_tasks,
        [
            "GH-C35",
            "session-runtime control-plane adapter",
            "raw transcripts, credentials, billing, permissions",
        ],
        source=CONTRIBUTOR_TASKS,
    )

    print("session-runtime-control-plane-adapter-doc-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
