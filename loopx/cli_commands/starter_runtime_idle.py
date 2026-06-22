from __future__ import annotations

import argparse
from pathlib import Path

from ..codex_cli_probe import (
    DEFAULT_MIN_HUMAN_INPUT_IDLE_SECONDS,
    build_codex_cli_runtime_idle_observation_payload,
    load_codex_cli_runtime_idle_fixture,
    probe_human_input_idle_seconds,
)


def _add_runtime_idle_observation_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_idle_fixture: bool = True,
) -> None:
    if include_idle_fixture:
        parser.add_argument(
            "--idle-fixture",
            help="Optional public-safe runtime idle fixture. Without it, later visible turn candidates remain blocked.",
        )
    parser.add_argument(
        "--observe-local-runtime",
        action="store_true",
        help="Build the idle packet from public-safe local observation fields instead of a JSON fixture.",
    )
    parser.add_argument(
        "--observed-surface",
        default="codex_cli_tui_visible_window",
        choices=[
            "codex_cli_tui_visible_window",
            "remote_control_visible_prompt",
            "same_tui_visible_attach",
            "visible_resume_prompt",
        ],
        help="Visible Codex CLI surface observed by the local runtime check.",
    )
    parser.add_argument(
        "--turn-state",
        choices=["idle", "running", "unknown"],
        default="unknown",
        help="Public-safe visible turn state. Unknown or running fails closed.",
    )
    parser.add_argument(
        "--human-input-idle-seconds",
        type=float,
        help="Public-safe observed seconds since last human input. Useful for tests or external sensors.",
    )
    parser.add_argument(
        "--probe-human-input-idle",
        action="store_true",
        help="Probe the local platform for coarse human-input idle seconds when supported.",
    )
    parser.add_argument(
        "--min-human-input-idle-seconds",
        type=float,
        default=DEFAULT_MIN_HUMAN_INPUT_IDLE_SECONDS,
        help="Minimum idle seconds required to consider human typing inactive.",
    )
    parser.add_argument(
        "--checked-before-prompt",
        action="store_true",
        help="Confirm this idle check ran before any later visible prompt.",
    )
    parser.add_argument(
        "--visible-to-user",
        action="store_true",
        help="Confirm the target turn remains visible to the user.",
    )
    parser.add_argument(
        "--user-can-interrupt",
        action="store_true",
        help="Confirm the user can interrupt the target turn.",
    )
    parser.add_argument(
        "--manual-takeover-available",
        action="store_true",
        help="Confirm manual takeover remains available.",
    )


def _load_codex_cli_runtime_idle_payload(args: argparse.Namespace) -> dict[str, object] | None:
    if args.idle_fixture and args.observe_local_runtime:
        raise ValueError("Use either --idle-fixture or --observe-local-runtime, not both.")
    if args.idle_fixture:
        return load_codex_cli_runtime_idle_fixture(Path(args.idle_fixture).expanduser())
    if not args.observe_local_runtime:
        return None
    probe_result = None
    human_input_idle_seconds = args.human_input_idle_seconds
    if args.probe_human_input_idle:
        probe_result = probe_human_input_idle_seconds()
        if probe_result.get("ok") is True:
            human_input_idle_seconds = float(probe_result["human_input_idle_seconds"])
    return build_codex_cli_runtime_idle_observation_payload(
        observed_surface=args.observed_surface,
        turn_state=args.turn_state,
        human_input_idle_seconds=human_input_idle_seconds,
        min_human_input_idle_seconds=args.min_human_input_idle_seconds,
        checked_before_prompt=bool(args.checked_before_prompt),
        visible_to_user=bool(args.visible_to_user),
        user_can_interrupt=bool(args.user_can_interrupt),
        manual_takeover_available=bool(args.manual_takeover_available),
        probe_result=probe_result,
    )
