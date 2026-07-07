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
from loopx.capabilities.auto_research.demo_e2e import _load_visible_wake_into_payload


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
        "--auto-wake",
    ):
        require(marker in source, f"auto-research CLI missing generic policy helper: {marker}")
    wake_callback = make_visible_wake_callback(tmux_bin="tmux")
    require(callable(wake_callback), "wake helper should return a callback")


def assert_visible_wake_loader_requires_prompt_delivery() -> None:
    delivered_payload: dict[str, object] = {"visible_worker_proof": {}}
    _load_visible_wake_into_payload(
        payload=delivered_payload,
        wake={
            "schema_version": "multi_agent_pane_a2a_wakeup_v0",
            "mode": "execute",
            "session_name": "fixture",
            "target_lanes": ["research-executor"],
            "coordination_model": "decentralized_state_a2a",
            "wakeup_model": "fixed_prompt_broadcast",
            "workflow_driver": False,
            "broadcaster_reads_frontier": False,
            "broadcaster_selects_todo": False,
            "pane_decision_owner": "codex_tui_agent_via_loopx_state",
            "pane_input_ready_verified": True,
            "ready_lanes": ["research-executor"],
            "not_ready_lanes": [],
            "prompt_submit_checks": [{"target": "%2", "retry_count": 0}],
            "prompt_delivery": "tmux_paste_buffer_after_codex_tui_first_turn_ready",
            "driver_contract": {
                "schema_version": "multi_agent_decentralized_a2a_driver_contract_v0",
                "owner_layer": "generic_multi_agent_kernel",
            },
        },
    )
    delivered_proof = delivered_payload["visible_worker_proof"]
    require(
        delivered_proof["cadence_wake_verified"] is True,
        "delivered wake should verify cadence wake",
    )
    require(
        delivered_proof["cadence_wake_prompt_delivered"] is True,
        "delivered wake should expose prompt delivery",
    )

    pending_payload: dict[str, object] = {"visible_worker_proof": {}}
    _load_visible_wake_into_payload(
        payload=pending_payload,
        wake={
            "schema_version": "multi_agent_pane_a2a_wakeup_v0",
            "mode": "execute",
            "session_name": "fixture",
            "target_lanes": ["research-executor"],
            "coordination_model": "decentralized_state_a2a",
            "wakeup_model": "fixed_prompt_broadcast",
            "workflow_driver": False,
            "broadcaster_reads_frontier": False,
            "broadcaster_selects_todo": False,
            "pane_decision_owner": "codex_tui_agent_via_loopx_state",
            "pane_input_ready_verified": False,
            "pane_input_ready_checks": [
                {
                    "lane": "research-executor",
                    "ready": False,
                    "not_ready_reason": "codex_tui_busy_or_not_ready",
                }
            ],
            "ready_lanes": [],
            "not_ready_lanes": ["research-executor"],
            "prompt_submit_checks": [],
            "prompt_delivery": "skipped_no_input_ready_panes",
            "driver_contract": {
                "schema_version": "multi_agent_decentralized_a2a_driver_contract_v0",
                "owner_layer": "generic_multi_agent_kernel",
            },
        },
    )
    pending_proof = pending_payload["visible_worker_proof"]
    pending_wake = pending_payload["visible_wake"]
    require(
        pending_proof["cadence_wake_verified"] is False,
        "busy/queued pane must not count as cadence wake verified",
    )
    require(
        pending_proof["cadence_wake_prompt_delivered"] is False,
        "busy/queued pane must expose no prompt delivery",
    )
    require(
        pending_proof["cadence_wake_pending_reason"] == "pane_not_ready",
        "busy/queued pane should expose a pending reason",
    )
    require(
        pending_proof["cadence_wake_not_ready_reasons"] == ["codex_tui_busy_or_not_ready"],
        "busy/queued pane should expose public-safe not-ready reasons",
    )
    require(
        pending_wake["prompt_delivered"] is False
        and pending_wake["not_ready_reasons"] == ["codex_tui_busy_or_not_ready"],
        "visible wake payload should preserve public-safe pending diagnostics",
    )


def main() -> None:
    assert_start_policy()
    assert_demo_policy_preserves_headless_visible_mix()
    assert_conflicts()
    assert_auto_research_consumes_generic_policy()
    assert_visible_wake_loader_requires_prompt_delivery()
    print("auto-research-visible-launch-policy-smoke ok")


if __name__ == "__main__":
    main()
