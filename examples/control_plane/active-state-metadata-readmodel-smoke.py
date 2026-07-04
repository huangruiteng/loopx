#!/usr/bin/env python3
"""Smoke-test active-state metadata read-model parity."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.projections import active_state_metadata as metadata_read_model  # noqa: E402


def main() -> None:
    state_text = """---
updated_at: "2026-07-04T10:00:00+08:00"
owner: codex
malformed
---

## Agent Todo
- [ ] keep working
"""
    assert status_module.parse_state_frontmatter(state_text) == metadata_read_model.parse_state_frontmatter(
        state_text
    )
    assert status_module.parse_state_frontmatter("no frontmatter") == {}
    assert status_module.parse_state_frontmatter("---\nmissing close") == {}

    headings = {
        "User Todo / Owner Review Reading Queue": "user",
        "Project Agent Todo": "agent",
        "Completed Work Archive": None,
        "普通章节": None,
    }
    for heading, expected in headings.items():
        assert status_module.todo_role_for_heading(heading) == expected, heading
        assert metadata_read_model.todo_role_for_heading(heading) == expected, heading

    print("active-state-metadata-readmodel-smoke ok")


if __name__ == "__main__":
    main()
