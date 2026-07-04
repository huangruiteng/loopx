#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.multi_agent.visible_launch_policy import (
    make_visible_wake_callback,
    resolve_codex_trust_workspace,
    resolve_visible_launch_policy,
)


AUTO_RESEARCH_CLI = ROOT / "loopx" / "capabilities" / "auto_research" / "cli.py"


def ns(**values: object) -> argparse.Namespace:
    defaults = {
        "attach": False,
        "no_attach": False,
        "wake_visible_after_launch": None,
        "codex_trust_workspace": None,
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_start_policy() -> None:
    policy = resolve_visible_launch_policy(
        ns(),
        launch_visible=True,
        default_wake_allowed=False,
        default_attach_allowed=True,
    )
    require(policy.launch_visible is True, "start should launch visible panes")
    require(policy.wake_visible_after_launch is False, "start first tick belongs to the visible TUI")
    require(policy.attach is True, "start should attach for operator-visible research")
    require(
        resolve_codex_trust_workspace(ns(), launch_visible=True, default=True) is True,
        "start default workspace should be trusted to avoid first-screen trust prompt",
    )

    takeover = resolve_visible_launch_policy(
        ns(attach=True),
        launch_visible=True,
        default_wake_allowed=False,
        default_attach_allowed=True,
    )
    require(takeover.wake_visible_after_launch is False, "operator takeover should not add a background wake")
    require(takeover.attach is True, "explicit attach should attach")


def assert_demo_policy_preserves_headless_visible_mix() -> None:
    policy = resolve_visible_launch_policy(
        ns(),
        launch_visible=True,
        default_wake_allowed=False,
        default_attach_allowed=False,
    )
    require(policy.launch_visible is True, "explicit visible launch should still launch")
    require(policy.wake_visible_after_launch is False, "headless visible mix should not default wake")
    require(policy.attach is False, "headless visible mix should not default attach")

    require(
        resolve_codex_trust_workspace(ns(), launch_visible=True, default=False) is False,
        "user-provided demo workspace should not be trusted by default",
    )
    require(
        resolve_codex_trust_workspace(
            ns(codex_trust_workspace=True),
            launch_visible=True,
            default=False,
        )
        is True,
        "explicit trust flag should override the workspace default",
    )


def assert_conflicts() -> None:
    try:
        resolve_visible_launch_policy(
            ns(attach=True, no_attach=True),
            launch_visible=True,
            default_wake_allowed=True,
            default_attach_allowed=True,
        )
    except ValueError as exc:
        require("--attach cannot be combined with --no-attach" in str(exc), str(exc))
    else:
        raise AssertionError("expected attach/no-attach conflict")

    try:
        resolve_visible_launch_policy(
            ns(attach=True, wake_visible_after_launch=True),
            launch_visible=True,
            default_wake_allowed=True,
            default_attach_allowed=True,
        )
    except ValueError as exc:
        require("--wake-visible-after-launch" in str(exc), str(exc))
    else:
        raise AssertionError("expected attach/wake conflict")


def assert_auto_research_consumes_generic_policy() -> None:
    source = AUTO_RESEARCH_CLI.read_text(encoding="utf-8")
    for removed in (
        "def _start_wake_visible_after_launch",
        "def _start_attach_visible",
        "def _start_codex_trust_workspace",
        "wake_visible_multi_agent_panes",
    ):
        require(removed not in source, f"auto-research CLI still owns generic visible policy: {removed}")
    for marker in (
        "resolve_visible_launch_policy",
        "resolve_codex_trust_workspace",
        "make_visible_wake_callback",
    ):
        require(marker in source, f"auto-research CLI missing generic policy helper: {marker}")
    wake_callback = make_visible_wake_callback(tmux_bin="tmux")
    require(callable(wake_callback), "wake helper should return a callback")


def main() -> None:
    assert_start_policy()
    assert_demo_policy_preserves_headless_visible_mix()
    assert_conflicts()
    assert_auto_research_consumes_generic_policy()
    print("auto-research-visible-launch-policy-smoke ok")


if __name__ == "__main__":
    main()
