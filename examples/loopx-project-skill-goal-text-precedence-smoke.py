#!/usr/bin/env python3
"""Guard the loopx-project skill against downgrading goal text to bare /loopx."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "loopx-project" / "SKILL.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = SKILL.read_text(encoding="utf-8")
    require("Recognized project-local goal-start command:" in text, "goal-start heading missing")
    require("- `/loopx <goal text>`" in text, "goal-text command missing")
    require("- `/loopx`\n" not in text, "bare /loopx should not be listed as project-local fallback")
    require("If there is any non-whitespace text after `/loopx`, it is goal text." in text, "goal text precedence missing")
    require("do not downgrade the\nrequest into a status or inspection turn" in text, "downgrade guard missing")
    require("Bare `/loopx` is read/status-first" not in text, "bare /loopx status-first branch should not steer this skill")
    print("loopx-project-skill-goal-text-precedence-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
