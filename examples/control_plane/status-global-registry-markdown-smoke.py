#!/usr/bin/env python3
"""Smoke-test global registry status markdown rendering."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.presentation.renderers.status_markdown import render_status_markdown  # noqa: E402


def main() -> None:
    markdown = render_status_markdown(
        {
            "ok": False,
            "registry": "./fixtures/registry.json",
            "runtime_root": "./fixtures/runtime",
            "goal_count": 1,
            "run_count": 1,
            "contract": {
                "ok": True,
                "summary": {"errors": 0, "warnings": 0, "checks": 8},
            },
            "global_registry": {
                "available": True,
                "ok": False,
                "summary": {"findings": 2, "high": 1, "action": 1, "info": 0},
                "findings": [
                    {
                        "severity": "action",
                        "kind": "source_registry_missing",
                        "goal_id": "fixture-goal",
                        "message": "registry source missing",
                        "recommended_action": "sync the source registry",
                    },
                    {
                        "severity": "info",
                        "kind": "global_registry_shadow",
                        "goal_ids": ["shadow-a", "shadow-b"],
                        "message": "shadow finding compacted",
                    },
                ],
            },
            "attention_queue": {"items": []},
            "run_history": {"goals": []},
        }
    )

    assert "global_registry: available=True, ok=False, findings=2" in markdown, markdown
    assert "## Global Registry Findings" in markdown, markdown
    assert "action source_registry_missing goal=fixture-goal: registry source missing" in markdown, markdown
    assert "action: sync the source registry" in markdown, markdown
    assert "info global_registry_shadow goal=['shadow-a', 'shadow-b']: shadow finding compacted" in markdown, markdown
    print("status-global-registry-markdown-smoke ok")


if __name__ == "__main__":
    main()
