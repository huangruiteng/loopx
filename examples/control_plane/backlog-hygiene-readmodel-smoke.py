#!/usr/bin/env python3
"""Smoke-test backlog hygiene warning read-model wrappers."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.projections.backlog_hygiene import (  # noqa: E402
    backlog_hygiene_warning as direct_backlog_hygiene_warning,
)
from loopx.status import (  # noqa: E402
    BACKLOG_HYGIENE_BULLET_PATTERN,
    BACKLOG_HYGIENE_HINT_PATTERN,
    BACKLOG_HYGIENE_SECTION_HEADINGS,
    MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS,
    active_state_sections,
    backlog_hygiene_warning,
    public_safe_compact_text,
)


STATE_TEXT = """# Goal

## Next Action

- Continue canary-gated cleanup

## Operating Lessons

- keep this as a plain note
- [P2] add a durable follow-up todo
"""


def direct_warning(agent_todos: dict[str, object] | None) -> dict[str, object] | None:
    return direct_backlog_hygiene_warning(
        STATE_TEXT,
        agent_todos=agent_todos,
        section_headings=BACKLOG_HYGIENE_SECTION_HEADINGS,
        section_parser=active_state_sections,
        bullet_pattern=BACKLOG_HYGIENE_BULLET_PATTERN,
        hint_pattern=BACKLOG_HYGIENE_HINT_PATTERN,
        public_safe_compact_text=public_safe_compact_text,
        max_evidence_items=MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS,
    )


def main() -> int:
    empty_agent_todos = {"open_count": 0}
    wrapper = backlog_hygiene_warning(STATE_TEXT, agent_todos=empty_agent_todos)
    direct = direct_warning(empty_agent_todos)
    assert wrapper == direct, (wrapper, direct)
    assert wrapper is not None, wrapper
    assert wrapper["kind"] == "hidden_backlog_without_agent_todo", wrapper
    assert wrapper["requires_agent_todo"] is True, wrapper
    assert wrapper["source_sections"] == ["Next Action", "Operating Lessons"], wrapper
    assert wrapper["evidence_count"] == 2, wrapper

    assert backlog_hygiene_warning(STATE_TEXT, agent_todos={"open_count": 1}) is None
    assert direct_warning({"open_count": 1}) is None

    no_backlog = "## Operating Lessons\n\n- just a calm observation\n"
    assert backlog_hygiene_warning(no_backlog, agent_todos={"open_count": 0}) is None

    print("backlog-hygiene-readmodel-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
