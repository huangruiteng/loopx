#!/usr/bin/env python3
"""Smoke-test the status markdown overview renderer seam."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.presentation.renderers.status_markdown import (  # noqa: E402
    append_status_overview_markdown,
)
from loopx.status import render_status_markdown  # noqa: E402


def overview_payload() -> dict:
    return {
        "ok": False,
        "registry": "/tmp/loopx-registry.json",
        "runtime_root": "/tmp/loopx-runtime",
        "goal_count": 2,
        "run_count": 7,
        "status_contract": {
            "schema_version": 2,
            "minimum_dashboard_schema_version": 2,
            "producer": "loopx status",
        },
        "goal_filter": "loopx-meta",
        "contract": {
            "ok": False,
            "summary": {
                "errors": 2,
                "warnings": 1,
                "checks": 8,
            },
            "errors": ["registry goals checked: 2"],
            "warnings": ["public boundary scan clean: 0 files"],
            "checks": ["status contract emitted"],
        },
        "contract_errors": [
            "missing dashboard status_contract",
            "stale registry pointer",
        ],
        "contract_errors_truncated": True,
        "contract_errors_total_count": 4,
        "contract_warnings": ["global registry has action findings"],
        "contract_warnings_truncated": True,
        "contract_warnings_total_count": 3,
        "global_registry": {
            "available": True,
            "ok": True,
            "summary": {
                "findings": 0,
                "high": 0,
                "action": 0,
                "info": 0,
            },
            "findings": [],
        },
        "attention_queue": {
            "item_count": 0,
            "needs_user_or_controller": 0,
            "needs_controller": 0,
            "needs_codex": 0,
            "watching_external_evidence": 0,
            "watching_monitor": 0,
        },
        "run_history": {
            "goal_count": 0,
            "run_count": 0,
            "goals": [],
        },
    }


def assert_overview(markdown: str) -> None:
    assert markdown.startswith("# LoopX Status\n\n"), markdown
    assert "- ok: `False`" in markdown, markdown
    assert "- registry: `/tmp/loopx-registry.json`" in markdown, markdown
    assert "- runtime_root: `/tmp/loopx-runtime`" in markdown, markdown
    assert "- goals: `2`" in markdown, markdown
    assert "- runs: `7`" in markdown, markdown
    assert (
        "- status_contract: schema_version=2, "
        "minimum_dashboard_schema_version=2, producer=loopx status"
    ) in markdown, markdown
    assert "- goal_filter: `loopx-meta`" in markdown, markdown
    assert "- contract: ok=False, errors=2, warnings=1, checks=8" in markdown, markdown
    assert "## Status Contract Signals" in markdown, markdown
    assert "- error: missing dashboard status_contract" in markdown, markdown
    assert "- error: stale registry pointer" in markdown, markdown
    assert "- contract_errors_truncated: total=4" in markdown, markdown
    assert "- warning: global registry has action findings" in markdown, markdown
    assert "- contract_warnings_truncated: total=3" in markdown, markdown


def assert_contract_details(markdown: str) -> None:
    assert "## Errors" in markdown, markdown
    assert "- registry goals checked: 2" in markdown, markdown
    assert "## Warnings" in markdown, markdown
    assert "- public boundary scan clean: 0 files" in markdown, markdown
    assert "## Checks" in markdown, markdown
    assert "- status contract emitted" in markdown, markdown


def main() -> int:
    payload = overview_payload()
    lines: list[str] = []
    append_status_overview_markdown(lines, payload)
    overview_markdown = "\n".join(lines)
    assert_overview(overview_markdown)
    assert "## Errors" not in overview_markdown, overview_markdown

    full_markdown = render_status_markdown(payload)
    assert_overview(full_markdown)
    assert_contract_details(full_markdown)
    print("status-overview-markdown-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
