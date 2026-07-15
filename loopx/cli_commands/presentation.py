from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..presentation.static_site import (
    StaticSiteContractError,
    package_static_site,
    rollback_static_site,
    verify_static_site_readback,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]], None
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _render_markdown(payload: dict[str, object]) -> str:
    lines = ["# LoopX Static Presentation", ""]
    for key in (
        "mode",
        "dry_run",
        "write_required",
        "write_performed",
        "semantic_noop",
        "active_revision",
        "previous_revision",
        "semantic_digest",
        "receipt_url",
        "verified",
        "attempts",
        "output_dir",
        "manifest_path",
        "receipt_path",
        "state_receipt_log",
    ):
        if key in payload:
            lines.append(f"- **{key}**: `{payload[key]}`")
    publisher = payload.get("publisher")
    if isinstance(publisher, dict):
        lines.extend(
            [
                f"- **publisher**: `{publisher.get('kind')}`",
                f"- **latest_url**: `{publisher.get('latest_url')}`",
                f"- **revision_url**: `{publisher.get('revision_url')}`",
            ]
        )
    return "\n".join(lines) + "\n"


def register_presentation_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "presentation",
        help="Package and verify provider-neutral static presentation artifacts.",
    )
    sub = parser.add_subparsers(dest="presentation_command", required=True)

    package = sub.add_parser(
        "package",
        help="Create stable latest/revision artifacts and a deploy receipt from a built site.",
    )
    add_subcommand_format(package)
    package.add_argument(
        "--site-dir", required=True, help="Already-built public-safe site directory."
    )
    package.add_argument(
        "--output-dir", required=True, help="Local publish artifact directory."
    )
    package.add_argument("--state-dir", help="Local deploy receipt state directory.")
    package.add_argument("--site-id", required=True, help="Stable public-safe site id.")
    package.add_argument(
        "--entry-path", default="index.html", help="Relative primary HTML entry."
    )
    package.add_argument(
        "--revision",
        help="Public-safe immutable revision id; defaults to the content digest.",
    )
    package.add_argument(
        "--publisher",
        choices=["local", "github-pages"],
        default="local",
        help="Optional publisher URL adapter. Local packaging is always available.",
    )
    package.add_argument(
        "--base-url", help="HTTPS deployment root required by github-pages."
    )
    package.add_argument(
        "--desktop-visual-check",
        required=True,
        choices=["passed"],
        help="Receipt from the desktop visual/overflow check.",
    )
    package.add_argument(
        "--mobile-visual-check",
        required=True,
        choices=["passed"],
        help="Receipt from the mobile visual/overflow check.",
    )
    package.add_argument(
        "--link-check",
        required=True,
        choices=["passed"],
        help="Receipt from the generated-link check.",
    )
    package.add_argument(
        "--execute",
        action="store_true",
        help="Write the local artifact and receipt state.",
    )

    rollback = sub.add_parser(
        "rollback",
        help="Prepare the latest artifact from a retained previous revision.",
    )
    add_subcommand_format(rollback)
    rollback.add_argument(
        "--output-dir", required=True, help="Existing local publish artifact directory."
    )
    rollback.add_argument("--state-dir", help="Local deploy receipt state directory.")
    rollback.add_argument(
        "--revision", help="Target retained revision; defaults to previous_revision."
    )
    rollback.add_argument(
        "--execute",
        action="store_true",
        help="Write the rollback artifact and receipt state.",
    )

    verify = sub.add_parser(
        "verify-readback",
        help="Compare a remote HTTP deploy receipt with the local packaged receipt.",
    )
    add_subcommand_format(verify)
    verify.add_argument(
        "--output-dir", required=True, help="Existing local publish artifact directory."
    )
    verify.add_argument("--state-dir", help="Local deploy receipt state directory.")
    verify.add_argument(
        "--receipt-url",
        help="Remote receipt URL; defaults to the publisher latest URL.",
    )
    verify.add_argument(
        "--retries", type=int, default=3, help="Bounded HTTP readback attempts (1-10)."
    )
    verify.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=1.0,
        help="Delay between attempts (0-30 seconds).",
    )
    verify.add_argument(
        "--execute",
        action="store_true",
        help="Persist the verified readback receipt locally.",
    )


def handle_presentation_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "presentation":
        return None
    try:
        if args.presentation_command == "package":
            payload = package_static_site(
                site_dir=Path(args.site_dir),
                output_dir=Path(args.output_dir),
                state_dir=Path(args.state_dir) if args.state_dir else None,
                site_id=args.site_id,
                entry_path=args.entry_path,
                revision=args.revision,
                publisher_kind=args.publisher,
                base_url=args.base_url,
                desktop_visual_check=args.desktop_visual_check,
                mobile_visual_check=args.mobile_visual_check,
                link_check=args.link_check,
                execute=args.execute,
            )
        elif args.presentation_command == "rollback":
            payload = rollback_static_site(
                output_dir=Path(args.output_dir),
                state_dir=Path(args.state_dir) if args.state_dir else None,
                revision=args.revision,
                execute=args.execute,
            )
        elif args.presentation_command == "verify-readback":
            payload = verify_static_site_readback(
                output_dir=Path(args.output_dir),
                state_dir=Path(args.state_dir) if args.state_dir else None,
                receipt_url=args.receipt_url,
                retries=args.retries,
                retry_delay_seconds=args.retry_delay_seconds,
                execute=args.execute,
            )
        else:
            raise StaticSiteContractError(
                f"unknown presentation command: {args.presentation_command}"
            )
    except StaticSiteContractError as exc:
        payload = {
            "ok": False,
            "mode": args.presentation_command,
            "error": str(exc),
        }
        print_payload(payload, output_format(args), _render_markdown)
        return 2
    print_payload(payload, output_format(args), _render_markdown)
    return 0
