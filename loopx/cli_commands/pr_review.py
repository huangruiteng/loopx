from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from ..capabilities.pr_review_queue import (
    build_pull_request_review_queue_observation,
)
from ..capabilities.pr_review_queue.result_check import check_review_result
from ..file_lock import exclusive_file_lock
from ..pr_review import (
    build_pr_review_packet,
    load_pr_fixture,
    normalize_pr_state_filter,
    render_pr_review_markdown,
    resolve_current_github_login,
    resolve_current_github_repository,
    scan_github_pull_requests,
)
from ..registry import atomic_write_json

PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
CHECKPOINT_SCHEMA_VERSION = "pull_request_review_monitor_checkpoint_v0"


def _file_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{label} must be an object")
    return payload


def _read_checkpoint(path: Path) -> tuple[dict[str, object] | None, str | None]:
    with exclusive_file_lock(path, operation="pr_review_checkpoint_read"):
        digest = _file_digest(path)
        if digest is None:
            return None, None
        payload = _read_json_object(path, label="observation state file")
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError("observation state file has an unsupported schema_version")
    return payload, digest


def _write_checkpoint(
    path: Path,
    *,
    expected_digest: str | None,
    repository: str | None,
    autonomous_review: dict[str, object],
) -> None:
    checkpoint = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "repository": repository,
        "autonomous_review": autonomous_review,
    }
    with exclusive_file_lock(path, operation="pr_review_checkpoint_write"):
        if _file_digest(path) != expected_digest:
            raise RuntimeError(
                "observation state changed concurrently; retry from the latest checkpoint"
            )
        atomic_write_json(path, checkpoint, preserve_mode=True)


def register_pr_review_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "pr-review",
        help="Build a public-safe /loopx-pr-review queue for the current project's open and merged pull requests.",
    )
    add_subcommand_format(parser)
    parser.add_argument(
        "--check-result",
        help="Check a saved review result for verdict/evidence consistency; no GitHub writes.",
    )
    parser.add_argument(
        "--packet",
        help="Saved pr-review packet required with --check-result; remote freshness is checked separately.",
    )
    parser.add_argument(
        "--repo",
        help="GitHub owner/repo to review. Defaults to the current project's gh repository context.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum PRs to include per selected lifecycle group.",
    )
    parser.add_argument(
        "--state",
        choices=("open", "merged", "all"),
        default="all",
        help="PR lifecycle state to include. Defaults to all so merged PRs remain reviewable.",
    )
    parser.add_argument(
        "--since",
        help="Only include PRs active since this ISO timestamp or YYYY-MM-DD date.",
    )
    parser.add_argument(
        "--fixture",
        help="Read public-safe PR metadata from a JSON fixture instead of live gh output.",
    )
    parser.add_argument(
        "--autonomous-observation",
        action="store_true",
        help="Add a read-only autonomous queue observation and at most one exact-head candidate.",
    )
    parser.add_argument(
        "--previous-observation-json",
        help="Compare against a prior autonomous observation or full pr-review packet.",
    )
    parser.add_argument(
        "--observation-state-file",
        help=(
            "Atomically persist and reuse one public-safe autonomous observation "
            "checkpoint across Codex tasks."
        ),
    )
    parser.add_argument(
        "--projected-exact-head",
        action="append",
        default=[],
        metavar="NUMBER@HEAD_OID",
        help=(
            "Acknowledge that one previously emitted exact-head candidate was "
            "durably projected to its Todo target. Repeatable."
        ),
    )
    parser.add_argument(
        "--handled-exact-head",
        action="append",
        default=[],
        metavar="NUMBER@HEAD_OID",
        help=(
            "Record one externally completed exact-head candidate so an autonomous "
            "monitor can advance to the next unhandled PR. Repeatable."
        ),
    )


def handle_pr_review_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "pr-review":
        return None
    checkpoint_path: Path | None = None
    try:
        if args.check_result or args.packet:
            if not (args.check_result and args.packet):
                raise ValueError("--check-result and --packet must be used together")
            if (
                args.autonomous_observation
                or args.observation_state_file
                or args.previous_observation_json
                or args.handled_exact_head
                or args.projected_exact_head
                or args.fixture
                or args.repo
                or args.since
            ):
                raise ValueError(
                    "result checking cannot be combined with scan or observation options"
                )
            try:
                saved_packet = _read_json_object(
                    Path(args.packet), label="review packet"
                )
                saved_result = _read_json_object(
                    Path(args.check_result), label="review result"
                )
            except OSError:
                raise ValueError(
                    "review packet or result is unreadable; check the supplied files"
                ) from None
            payload = check_review_result(saved_packet, saved_result)
            print_payload(
                payload, output_format(args), lambda value: json.dumps(value, indent=2)
            )
            return 0 if payload["ok"] else 1
        if args.previous_observation_json and not args.autonomous_observation:
            raise ValueError(
                "--previous-observation-json requires --autonomous-observation"
            )
        if args.handled_exact_head and not args.autonomous_observation:
            raise ValueError("--handled-exact-head requires --autonomous-observation")
        if args.projected_exact_head and not args.autonomous_observation:
            raise ValueError("--projected-exact-head requires --autonomous-observation")
        if args.observation_state_file and not args.autonomous_observation:
            raise ValueError(
                "--observation-state-file requires --autonomous-observation"
            )
        if args.observation_state_file and args.previous_observation_json:
            raise ValueError(
                "--observation-state-file cannot be combined with "
                "--previous-observation-json"
            )
        previous_observation = None
        checkpoint_digest = None
        if args.observation_state_file:
            checkpoint_path = Path(args.observation_state_file).expanduser()
            previous_observation, checkpoint_digest = _read_checkpoint(checkpoint_path)
        if args.previous_observation_json:
            previous_observation = _read_json_object(
                Path(args.previous_observation_json).expanduser(),
                label="previous observation JSON",
            )
        repository = args.repo
        source = "github_cli"
        reviewer_login = None
        if args.fixture:
            repository_from_fixture, pull_requests = load_pr_fixture(
                Path(args.fixture).expanduser()
            )
            repository = repository or repository_from_fixture
            source = "fixture"
            source_scan = None
        else:
            repository = repository or resolve_current_github_repository()
            reviewer_login = resolve_current_github_login()
            if args.autonomous_observation and not reviewer_login:
                raise RuntimeError(
                    "authenticated GitHub reviewer identity is required for "
                    "autonomous author-owned scheduling"
                )
            source_scan = scan_github_pull_requests(
                repo=repository,
                limit=max(1, args.limit) + 1,
                state_filter=normalize_pr_state_filter(args.state),
                since=args.since,
            )
            pull_requests = source_scan["pull_requests"]
        if checkpoint_path is not None and previous_observation:
            checkpoint_repository = str(
                previous_observation.get("repository") or ""
            ).strip()
            if (
                checkpoint_repository
                and checkpoint_repository != str(repository or "").strip()
            ):
                raise ValueError(
                    "observation state repository does not match the requested repository"
                )
        payload = build_pr_review_packet(
            pull_requests=pull_requests,
            repository=repository,
            limit=max(1, args.limit),
            source=source,
            state_filter=normalize_pr_state_filter(args.state),
            since=args.since,
            source_scan=source_scan,
            reviewer_login=reviewer_login,
        )
        if args.autonomous_observation:
            autonomous_review = build_pull_request_review_queue_observation(
                repository=repository,
                pull_requests=payload.get("pull_requests") or [],
                result_completeness=payload.get("result_completeness") or {},
                previous_observation=previous_observation,
                handled_exact_heads=args.handled_exact_head,
                projected_exact_heads=args.projected_exact_head,
                authenticated_developer_login=reviewer_login,
            )
            payload["autonomous_review"] = autonomous_review
            payload["request"]["autonomous_observation"] = True
            payload["request"]["previous_observation_supplied"] = bool(
                previous_observation
            )
            payload["request"]["handled_exact_head_count_supplied"] = len(
                args.handled_exact_head
            )
            payload["request"]["projected_exact_head_count_supplied"] = len(
                args.projected_exact_head
            )
            payload["request"]["observation_state_file_supplied"] = bool(
                checkpoint_path
            )
            payload["request"]["include"].append("autonomous_review")
            if checkpoint_path is not None:
                _write_checkpoint(
                    checkpoint_path,
                    expected_digest=checkpoint_digest,
                    repository=repository,
                    autonomous_review=autonomous_review,
                )
                payload["request"]["local_checkpoint_write_performed"] = True
    except Exception as exc:
        error = str(exc)
        if checkpoint_path is not None:
            path_candidates = {str(checkpoint_path)}
            with suppress(OSError):
                path_candidates.add(str(checkpoint_path.resolve()))
            for path_text in sorted(path_candidates, key=len, reverse=True):
                if path_text:
                    error = error.replace(path_text, "<observation-state-file>")
        payload = {
            "ok": False,
            "schema_version": "loopx_pr_review_command_response_v0",
            "request": {
                "schema_version": "loopx_pr_review_command_request_v0",
                "command": "/loopx-pr-review",
                "cli_command": "loopx pr-review [--repo owner/repo] [--state open|merged|all] [--since ISO]",
                "repository": args.repo,
                "limit": max(1, args.limit),
                "state_filter": normalize_pr_state_filter(args.state),
                "since": args.since,
                "source": "fixture" if args.fixture else "github_cli",
                "privacy_mode": "public_safe_github_metadata",
                "dry_run": True,
            },
            "error": error,
        }
    print_payload(payload, output_format(args), render_pr_review_markdown)
    return 0 if payload.get("ok") else 1
