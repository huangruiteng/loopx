#!/usr/bin/env python3
"""Guard the canary-promotion no-write path keeps promotion-gate coverage."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CANARY_SMOKE = REPO_ROOT / "examples" / "canary" / "canary-promotion-readiness-smoke.py"
DASHBOARD_DEMO_SMOKE = REPO_ROOT / "examples" / "dashboard-demo-readiness-smoke.py"


def assert_contains(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        raise AssertionError(f"missing {label}: {snippet}")


def assert_before(text: str, first: str, second: str, label: str) -> None:
    first_index = text.find(first)
    second_index = text.find(second)
    if first_index < 0 or second_index < 0:
        raise AssertionError(f"missing ordered snippets for {label}")
    if first_index >= second_index:
        raise AssertionError(f"wrong order for {label}: {first!r} must appear before {second!r}")


def main() -> int:
    canary_source = CANARY_SMOKE.read_text(encoding="utf-8")
    dashboard_source = DASHBOARD_DEMO_SMOKE.read_text(encoding="utf-8")

    assert_contains(canary_source, "--no-write-evidence", "canary no-write flag")
    assert_contains(canary_source, "--agent-id", "canary refresh-state agent id flag")
    assert_contains(canary_source, "DEFAULT_READINESS_AGENT_ID", "canary default writeback agent")
    assert_contains(canary_source, "DEFAULT_READINESS_AGENT_LANE", "canary default writeback lane")
    assert_contains(canary_source, "dashboard-demo-readiness-smoke.py", "canary dashboard demo-readiness command")
    assert_contains(canary_source, 'commands.append(("dashboard demo readiness", dashboard_command))', "canary grouped path append")
    assert_before(
        canary_source,
        'commands.append(("dashboard demo readiness", dashboard_command))',
        "if not args.no_write_evidence:",
        "canary grouped path before evidence writeback",
    )

    assert_contains(dashboard_source, "promotion gate structured contract", "demo promotion gate label")
    assert_contains(dashboard_source, "examples/promotion-gate-smoke.py", "demo promotion gate smoke")
    assert_before(
        dashboard_source,
        "promotion gate structured contract",
        "BROWSER_COMMANDS = [",
        "promotion gate stays in non-browser base group",
    )

    print("canary-promotion-no-write-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
