from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from importlib import import_module

REQUIRED_EXPORTS = {
    "loopx.extensions.lark.event_collector": (
        "inspect_lark_event_collector",
        "install_lark_event_collector",
        "plan_lark_event_collector",
    ),
    "loopx.extensions.lark.event_collector_runtime": ("run_lark_event_collector",),
    "loopx.extensions.lark.event_inbox": (
        "acknowledge_lark_event_inbox",
        "ingest_lark_event_inbox",
        "inspect_lark_event_inbox",
        "project_lark_event_inbox_urgency",
    ),
    "loopx.extensions.lark.inbox_reply": (
        "reply_lark_event_inbox",
        "send_lark_inbox_message",
    ),
    "loopx.extensions.lark.inbox_reactions": (
        "complete_lark_event_inbox_reactions",
        "mark_lark_event_inbox_processing",
    ),
    "loopx.extensions.lark.reviewer_notification": ("lark_reviewer_notification_sink",),
    "loopx.extensions.lark.goal_channel": (
        "deliver_goal_channel_payload",
        "doctor_lark_goal_channel",
        "notify_lark_goal_channel_gate",
        "prepare_goal_channel_payload",
        "setup_lark_goal_channel",
        "sync_lark_goal_channel",
    ),
    "loopx.extensions.lark.presentation.periodic_report": (
        "periodic_report_lark_sink_adapter",
        "periodic_report_miaoda_html_sink_adapter",
    ),
    "loopx.extensions.lark.periodic_report_delivery": (
        "deliver_periodic_report_to_goal_channel",
    ),
    "loopx.extensions.lark.periodic_report_request": (
        "bind_lark_periodic_report_source",
        "build_lark_periodic_report_hook_adapter",
        "settle_lark_periodic_report_source",
    ),
    "loopx.extensions.lark.presentation.kanban": (
        "lark_kanban_doctor",
        "sync_loopx_projection_to_lark_kanban",
        "sync_loopx_todos_to_lark_kanban",
    ),
    "loopx.extensions.lark.presentation.explore_results": (
        "setup_lark_explore_board",
        "sync_explore_results_to_lark",
        "sync_explore_visuals_to_lark",
    ),
}


def doctor_lark_provider() -> None:
    for module_name, exports in REQUIRED_EXPORTS.items():
        module = import_module(module_name)
        missing = [
            name for name in exports if not callable(getattr(module, name, None))
        ]
        if missing:
            raise RuntimeError(
                f"Lark provider module `{module_name}` is missing exports {missing}"
            )


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoopX Lark extension provider.")
    parser.add_argument("--doctor", action="store_true")
    args = parser.parse_args(argv)
    if not args.doctor:
        raise ValueError(
            "the Lark subprocess protocol is not active; use the LoopX compatibility CLI"
        )
    doctor_lark_provider()
    return 0


def main() -> int:
    try:
        return run()
    # The provider executable is a process boundary: redact every implementation
    # failure to its public exception type instead of leaking payload details.
    except Exception as exc:  # noqa: BLE001
        print(f"LoopX Lark provider failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
