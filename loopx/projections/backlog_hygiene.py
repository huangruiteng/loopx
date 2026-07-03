from __future__ import annotations

import re
from typing import Any, Callable, Optional


CompactText = Callable[..., Optional[str]]
SectionParser = Callable[[str, tuple[str, ...]], dict[str, list[str]]]


def backlog_hygiene_warning(
    state_text: str,
    *,
    agent_todos: dict[str, Any] | None,
    section_headings: tuple[str, ...],
    section_parser: SectionParser,
    bullet_pattern: re.Pattern[str],
    hint_pattern: re.Pattern[str],
    public_safe_compact_text: CompactText,
    max_evidence_items: int,
) -> dict[str, Any] | None:
    try:
        agent_open_count = int(agent_todos.get("open_count") or 0) if isinstance(agent_todos, dict) else 0
    except (TypeError, ValueError):
        agent_open_count = 0
    if agent_open_count > 0:
        return None

    evidence: list[dict[str, Any]] = []
    sections = section_parser(state_text, section_headings)
    for section, lines in sections.items():
        for line in lines:
            bullet_match = bullet_pattern.match(line)
            if not bullet_match:
                continue
            text = public_safe_compact_text(bullet_match.group(1), limit=220)
            if not text:
                continue
            if section.lower() == "next action" or hint_pattern.search(text):
                evidence.append({"section": section, "text": text})

    if not evidence:
        return None

    source_sections = sorted({str(item.get("section") or "") for item in evidence if item.get("section")})
    return {
        "kind": "hidden_backlog_without_agent_todo",
        "requires_agent_todo": True,
        "source_sections": source_sections,
        "agent_open_count": agent_open_count,
        "evidence_count": len(evidence),
        "first_evidence": evidence[:max_evidence_items],
        "recommended_action": (
            "mirror durable follow-up work into Agent Todo before heartbeat scheduling relies on "
            "Next Action or Operating Lessons"
        ),
    }
