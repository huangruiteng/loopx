from __future__ import annotations

from typing import Any


PROJECT_AGENT_HANDOFF_BUDGET = {
    "mode": "project_agent_handoff",
    "max_lines": 16,
    "max_chars": 1_800,
}


def handoff_budget_contract() -> dict[str, Any]:
    return dict(PROJECT_AGENT_HANDOFF_BUDGET)


def build_handoff_interface_budget(handoff_text: str) -> dict[str, Any]:
    budget = handoff_budget_contract()
    line_count = len(handoff_text.splitlines())
    char_count = len(handoff_text)
    return {
        **budget,
        "line_count": line_count,
        "char_count": char_count,
        "within_line_budget": line_count <= int(budget["max_lines"]),
        "within_char_budget": char_count <= int(budget["max_chars"]),
        "within_budget": line_count <= int(budget["max_lines"]) and char_count <= int(budget["max_chars"]),
    }
