#!/usr/bin/env python3
"""Smoke-test public-safe Terminal-Bench candidate routing packets.

This replaces per-packet one-off smokes. The routing packets are useful
historical evidence, but each packet's exact candidate ordering is not a
standalone product contract. Keep the long-lived validation focused on shared
public/private and no-upload invariants.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
README = TOPIC_DIR / "README.md"

COMMON_REQUIRED_SNIPPETS = (
    "public-safe",
    "no-upload",
    "raw logs",
    "trajectories",
    "credentials",
    "leaderboard",
    "Codex goal",
    "LoopX",
    "Select",
    "repeat",
    "treatment",
    "baseline",
)

FORBIDDEN_TEXT = (
    "/" + "Users/",
    "/" + "private/",
    ".local/" + "private-benchmark-jobs",
    ".cache/" + "harbor/tasks",
    "OPENAI" + "_API_KEY=",
    "CODEX" + "_AUTH",
    "auth" + ".json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "sk-" + "example",
)

REMOVED_ONE_OFF_SMOKE_MARKERS = (
    "terminal-bench-next-candidate-selection-smoke.py",
    "terminal-bench-next-candidate-after-install-windows-smoke.py",
    "terminal-bench-next-candidate-after-financial-document-processor-smoke.py",
    "terminal-bench-next-candidate-after-multi-source-data-merger-smoke.py",
    "terminal-bench-next-candidate-after-db-wal-recovery-smoke.py",
    "terminal-bench-next-candidate-after-build-cython-ext-smoke.py",
    "terminal-bench-next-candidate-after-pytorch-env-setup-smoke.py",
    "terminal-bench-next-candidate-after-regex-log-smoke.py",
    "terminal-bench-next-candidate-after-large-scale-text-editing-smoke.py",
)


def main() -> None:
    readme = README.read_text(encoding="utf-8")
    docs = sorted(TOPIC_DIR.glob("terminal-bench-next-candidate*.md"))
    assert len(docs) >= 9, [doc.name for doc in docs]

    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        assert doc.name in readme, doc.name

        missing = [snippet for snippet in COMMON_REQUIRED_SNIPPETS if snippet not in text]
        assert not missing, (doc.name, missing)

        leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
        assert not leaked, (doc.name, leaked)

        obsolete = [marker for marker in REMOVED_ONE_OFF_SMOKE_MARKERS if marker in text]
        assert not obsolete, (doc.name, obsolete)

    print(f"terminal-bench-candidate-routing-packets-smoke ok docs={len(docs)}")


if __name__ == "__main__":
    main()
