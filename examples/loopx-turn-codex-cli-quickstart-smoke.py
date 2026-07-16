#!/usr/bin/env python3
"""Keep the LoopX Turn partner quickstart small and concept-frozen."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
QUICKSTART = REPO_ROOT / "docs" / "product" / "loopx-turn-codex-cli-quickstart.md"


def main() -> int:
    text = QUICKSTART.read_text(encoding="utf-8")
    compact_text = " ".join(text.split())
    product_index = (REPO_ROOT / "docs" / "product" / "README.md").read_text(
        encoding="utf-8"
    )
    docs_index = (REPO_ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert len(text.splitlines()) <= 110, "quickstart must remain one page"
    for required in [
        "Agent CLI adapter",
        "Independent validator",
        "One Turn command",
        "loopx turn run-once",
        "--host codex-cli",
        "--validation-command-json",
        "status=committed",
        "result_kind=repair_required",
        "result_kind=replan_required",
        "result_kind=wait",
        "result_kind=user_action_required",
        "turn_key",
        "raw event stream",
        "they do not become new Turn states",
        "a scenario owner",
        "loopx-turn-codex-cli-e2e-smoke.py",
        "codex_cli_model_requires_newer_codex",
    ]:
        assert required in compact_text, required

    opening = "\n".join(text.splitlines()[:50])
    for internal_concept in [
        "TurnEnvelope",
        "scheduler hint",
        "journal",
        "resume eligibility",
        "benchmark bridge",
    ]:
        assert internal_concept not in opening, internal_concept

    link = "loopx-turn-codex-cli-quickstart.md"
    assert link in product_index, "product index link"
    assert f"product/{link}" in docs_index, "docs index link"

    print("loopx-turn-codex-cli-quickstart-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
