#!/usr/bin/env python3
"""Smoke-check guarded self-repair issue escalation stays safe and bounded."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "loopx-self-repair" / "SKILL.md"
REFERENCE = (
    ROOT
    / "skills"
    / "loopx-self-repair"
    / "references"
    / "upstream-issue-escalation.md"
)


def require(text: str, snippets: list[str], *, source: Path) -> None:
    missing = [snippet for snippet in snippets if snippet not in text]
    assert not missing, f"{source}: missing {missing}"


def main() -> int:
    skill = SKILL.read_text(encoding="utf-8")
    reference = REFERENCE.read_text(encoding="utf-8")

    require(
        skill,
        [
            "## Upstream Issue Escalation",
            "references/upstream-issue-escalation.md",
            "Invoking this skill never grants publication permission",
            "search open and closed issues",
            "create at most one issue per repair turn",
        ],
        source=SKILL,
    )
    require(
        reference,
        [
            "Self-repair invocation is diagnosis consent, not publication consent.",
            "LOOPX_SELF_REPAIR_AUTO_ISSUE=1",
            "credentials, suspected vulnerabilities",
            "loopx check --scan-path",
            "<!-- loopx-self-repair:fingerprint=<12-hex-sha256> -->",
            "gh issue list",
            "--state all",
            "gh auth status",
            "gh issue create",
            "Create at most one issue per repair turn",
            "upstream_issue_deduplicated",
            "upstream_issue_opened",
        ],
        source=REFERENCE,
    )

    search_position = reference.index("gh issue list")
    auth_position = reference.index("gh auth status")
    create_position = reference.index("gh issue create")
    assert search_position < auth_position < create_position, (
        "duplicate search and auth must precede issue creation"
    )

    print("self-repair-upstream-issue-escalation-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
