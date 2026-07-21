"""Public-safe case contracts for LoopX Turn Advisor qualification."""

from __future__ import annotations

from typing import Any


TURN_ADVISOR_CASE_SPECS: dict[str, dict[str, Any]] = {
    "marker-step": {
        "todo": (
            "Advance `docs/turn-e2e-marker.txt` by exactly one numbered step per "
            "Turn, starting at `loopx-turn-real-e2e-step-1`."
        ),
        "write_scope": ["docs/turn-e2e-marker.txt"],
        "files": {},
    },
    "arithmetic-fix": {
        "todo": (
            "Fix `calculator.py` so `add(a, b)` returns the mathematical sum for "
            "positive and negative integers. Keep the change limited to that file."
        ),
        "write_scope": ["calculator.py"],
        "files": {"calculator.py": "def add(a, b):\n    return a - b\n"},
    },
    "json-normalization": {
        "todo": (
            "Normalize `config/settings.json`: `enabled` must be JSON boolean true "
            "and `retries` must be JSON integer 3. Preserve valid JSON."
        ),
        "write_scope": ["config/settings.json"],
        "files": {"config/settings.json": '{"enabled":"yes","retries":"3"}\n'},
    },
    "multi-file-docs": {
        "todo": (
            "Promote the guide to stable: set `docs/guide.md` status to stable and "
            "replace the draft index entry with a relative Markdown link labelled Guide."
        ),
        "write_scope": ["docs/guide.md", "docs/index.md"],
        "files": {
            "docs/guide.md": "# Guide\n\nStatus: draft\n",
            "docs/index.md": "# Index\n\n- Guide (draft)\n",
        },
    },
    "bounded-refactor": {
        "todo": (
            "Refactor `names.py` to extract one private `_slug` helper and make both "
            "public functions delegate to it without changing their behavior."
        ),
        "write_scope": ["names.py"],
        "files": {
            "names.py": (
                "def user_slug(value):\n"
                "    return value.strip().lower().replace(\" \", \"-\")\n\n"
                "def project_slug(value):\n"
                "    return value.strip().lower().replace(\" \", \"-\")\n"
            )
        },
    },
}
TURN_ADVISOR_CASE_IDS = tuple(TURN_ADVISOR_CASE_SPECS)
