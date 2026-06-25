from __future__ import annotations

import argparse
from collections.abc import Callable

from .github_public import (
    build_github_public_channel_probe_packet,
    build_value_connector_install_check_packet,
    render_github_public_channel_probe_markdown,
    render_value_connector_install_check_markdown,
)
from .planner import (
    ALLOWED_CONNECTOR_KINDS,
    ALLOWED_STAGES,
    ALLOWED_VALUE_AXES,
    build_single_value_connector_plan,
    build_value_connector_plan_fixture,
    build_value_connector_plan_packet,
    render_value_connector_plan_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_value_connector_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "value-connectors",
        help="Plan reusable external-value connector calls before execution.",
    )
    sub = parser.add_subparsers(dest="value_connectors_command", required=True)
    install_parser = sub.add_parser(
        "install-check",
        help="Show connector install/use steps and local dependency status.",
    )
    add_subcommand_format(install_parser)
    install_parser.add_argument(
        "--connector",
        choices=[
            "all",
            "github_public_channel",
            "botmail_identity",
            "community_channel",
            "social_browser_x",
        ],
        default="all",
        help="Connector profile to check.",
    )
    plan_parser = sub.add_parser(
        "plan",
        help="Render a public-safe connector call plan with gates and value metrics.",
    )
    add_subcommand_format(plan_parser)
    plan_parser.add_argument(
        "--generated-at",
        default="2026-06-25T00:00:00Z",
        help="Public-safe generated_at timestamp for the plan.",
    )
    plan_parser.add_argument(
        "--scenario",
        default="external_value_channel_queue",
        help="Fixture scenario label when --connector-id is omitted.",
    )
    plan_parser.add_argument("--connector-id", help="Build a single-call plan for this connector id.")
    plan_parser.add_argument(
        "--connector-kind",
        choices=sorted(ALLOWED_CONNECTOR_KINDS),
        default="custom_connector",
        help="Connector kind for --connector-id single-call plans.",
    )
    plan_parser.add_argument("--channel", help="Channel label for a single-call plan.")
    plan_parser.add_argument(
        "--stage",
        choices=sorted(ALLOWED_STAGES),
        default="observe",
        help="Connector stage for a single-call plan.",
    )
    plan_parser.add_argument("--target-ref", help="Public-safe target label for a single-call plan.")
    plan_parser.add_argument("--target-url", help="Optional public https target URL without query or fragment.")
    plan_parser.add_argument(
        "--value-axis",
        choices=sorted(ALLOWED_VALUE_AXES),
        default="revenue",
        help="Primary value axis for a single-call plan.",
    )
    plan_parser.add_argument("--money-metric", help="Required money/cost/demand proxy for a single-call plan.")
    plan_parser.add_argument("--success-metric", help="Required success metric for a single-call plan.")
    plan_parser.add_argument("--kill-condition", help="Required stop condition for a single-call plan.")
    plan_parser.add_argument(
        "--audience",
        default="external operators running long-lived agent workflows",
        help="Public-safe target audience label.",
    )
    plan_parser.add_argument(
        "--sender-identity",
        default="LoopX operator",
        help="Public-safe sender identity label for the plan.",
    )
    plan_parser.add_argument(
        "--external-read",
        action="store_true",
        help="Declare that the future connector call would need a bounded external metadata read.",
    )
    plan_parser.add_argument(
        "--external-write-requested",
        action="store_true",
        help="Declare that the future connector call requests an external write gate.",
    )
    github_parser = sub.add_parser(
        "github-public-probe",
        help="Probe public GitHub issue/PR/discussion metadata without external writes.",
    )
    add_subcommand_format(github_parser)
    github_parser.add_argument(
        "--url",
        required=True,
        help=(
            "Public GitHub issue, PR, or discussion URL. Query strings, fragments, "
            "auth material, and non-github.com hosts are rejected."
        ),
    )
    github_parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help=(
            "Perform the bounded metadata read. Issue/PR uses GitHub REST; "
            "discussion uses gh GraphQL when available."
        ),
    )
    github_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Network/tool timeout for --fetch-metadata.",
    )


def handle_value_connector_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "value-connectors":
        return None
    try:
        if args.value_connectors_command == "install-check":
            payload = build_value_connector_install_check_packet(
                connector=args.connector,
            )
            print_payload(
                payload,
                output_format(args),
                render_value_connector_install_check_markdown,
            )
            return 0
        if args.value_connectors_command == "github-public-probe":
            payload = build_github_public_channel_probe_packet(
                url=args.url,
                fetch_metadata=args.fetch_metadata,
                timeout_seconds=args.timeout_seconds,
            )
            print_payload(
                payload,
                output_format(args),
                render_github_public_channel_probe_markdown,
            )
            return 0 if payload.get("ok") else 1
        if args.value_connectors_command != "plan":
            raise ValueError("value-connectors requires `install-check`, `plan`, or `github-public-probe`")
        if args.connector_id:
            missing = [
                name
                for name in (
                    "channel",
                    "target_ref",
                    "money_metric",
                    "success_metric",
                    "kill_condition",
                )
                if not getattr(args, name)
            ]
            if missing:
                raise ValueError(
                    "single-call plan requires " + ", ".join(f"--{name.replace('_', '-')}" for name in missing)
                )
            plan = build_single_value_connector_plan(
                connector_id=args.connector_id,
                connector_kind=args.connector_kind,
                channel=args.channel,
                stage=args.stage,
                target_ref=args.target_ref,
                target_url=args.target_url,
                audience=args.audience,
                sender_identity=args.sender_identity,
                value_axis=args.value_axis,
                money_metric=args.money_metric,
                success_metric=args.success_metric,
                kill_condition=args.kill_condition,
                generated_at=args.generated_at,
                external_reads_allowed=args.external_read,
                external_write_requested=args.external_write_requested,
            )
        else:
            plan = build_value_connector_plan_fixture(
                generated_at=args.generated_at,
                scenario=args.scenario,
            )
        payload = build_value_connector_plan_packet(plan)
    except Exception as exc:
        if getattr(args, "value_connectors_command", None) == "github-public-probe":
            payload = {
                "ok": False,
                "schema_version": "github_public_channel_probe_error_v0",
                "mode": "github-public-channel-probe",
                "error": str(exc),
                "external_reads_performed": False,
                "external_writes_performed": False,
            }
            print_payload(payload, output_format(args), render_github_public_channel_probe_markdown)
            return 1
        payload = {"ok": False, "schema_version": "value_connector_plan_error_v0", "error": str(exc)}
        print_payload(payload, output_format(args), render_value_connector_plan_markdown)
        return 1
    print_payload(payload, output_format(args), render_value_connector_plan_markdown)
    return 0
