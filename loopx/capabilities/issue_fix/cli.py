from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...agent_registry import load_goal_from_registry
from ...boundary_authority import checkpointed_boundary_authority_summary
from ...domain_packs.issue_fix import (
    default_issue_fix_domain_state_ledger_path,
    default_issue_fix_feasibility_ledger_path,
    upsert_issue_fix_feasibility_ledger_jsonl,
    upsert_issue_fix_pr_lifecycle_ledger_jsonl,
)
from .acceptance_loop import (
    build_issue_fix_acceptance_fixture_packet,
    build_issue_fix_caller_repo_branch_packet,
    build_issue_fix_repo_branch_fixture_packet,
    render_issue_fix_acceptance_loop_markdown,
)
from .feasibility import (
    build_issue_fix_feasibility_packet,
    render_issue_fix_feasibility_markdown,
)
from .outcome_projection import (
    build_issue_fix_outcome_projection,
    render_issue_fix_outcome_projection_markdown,
)
from .pr_lifecycle import (
    build_issue_fix_pr_lifecycle_monitor_packet,
    render_issue_fix_pr_lifecycle_monitor_markdown,
)
from .reviewer_recommendation import (
    build_issue_fix_reviewer_recommendation_packet,
    render_issue_fix_reviewer_recommendation_markdown,
)
from .reviewer_request import (
    build_issue_fix_reviewer_request_packet,
    render_issue_fix_reviewer_request_markdown,
)
from .workflow_plan import (
    build_issue_fix_workflow_plan_packet,
    render_issue_fix_workflow_plan_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _load_json_object(path_text: str) -> dict[str, Any]:
    if path_text == "-":
        payload = json.loads(sys.stdin.read())
    else:
        payload = json.loads(Path(path_text).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path_text} must contain a JSON object")
    return payload


def _load_jsonl_row(
    path: Path,
    *,
    repo: str,
    ref_field: str,
    ref_value: str,
) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"issue-fix domain-state source is missing: {path.name}")
    match: dict[str, Any] | None = None
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_number} is not valid JSON") from exc
        observation = row.get("observation") if isinstance(row, dict) else None
        if not isinstance(observation, dict):
            continue
        if (
            str(observation.get("repo") or "").strip() == repo
            and str(observation.get(ref_field) or "").strip() == ref_value
        ):
            match = row
    if match is None:
        raise ValueError(
            f"{path.name} has no row for repo={repo} {ref_field}={ref_value}"
        )
    return match


def _goal_boundary_authority_projection(
    *,
    registry_path: Path | None,
    goal_id: str | None,
) -> tuple[list[str], bool]:
    if registry_path is None or not goal_id:
        return [], False
    goal = load_goal_from_registry(registry_path, goal_id)
    if not isinstance(goal, dict):
        return [], False
    coordination = (
        goal.get("coordination")
        if isinstance(goal.get("coordination"), dict)
        else {}
    )
    summary = checkpointed_boundary_authority_summary(coordination)
    scopes = (
        list(summary.get("active_write_scope") or [])
        if isinstance(summary, dict)
        else []
    )
    return [str(scope) for scope in scopes], True


def register_issue_fix_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    issue_fix_parser = subparsers.add_parser(
        "issue-fix",
        help="Run public-safe issue fix acceptance loops.",
    )
    issue_fix_sub = issue_fix_parser.add_subparsers(
        dest="issue_fix_command",
        required=True,
    )
    workflow_parser = issue_fix_sub.add_parser(
        "workflow-plan",
        help=(
            "Plan the full issue-fix workflow from public metadata to ordered "
            "LoopX todos, validation, and PR review packet readiness without writes."
        ),
    )
    add_subcommand_format(workflow_parser)
    workflow_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the issue metadata.",
    )
    workflow_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue or PR reference label.",
    )
    workflow_parser.add_argument(
        "--url",
        default=None,
        help="Optional https://github.com/owner/repo/issues/123 or /pull/123 URL.",
    )
    workflow_parser.add_argument(
        "--metadata-json",
        default=None,
        help=(
            "Path to mocked provider JSON metadata, or '-' for stdin. "
            "Body/comment fields stay gated and are not copied."
        ),
    )
    workflow_parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help=(
            "Explicitly fetch public GitHub issue/PR metadata with gh api --jq. "
            "Only body-free metadata fields are captured."
        ),
    )
    workflow_parser.add_argument(
        "--fetch-timeout-seconds",
        type=int,
        default=10,
        help="Timeout for --fetch-metadata.",
    )
    workflow_parser.add_argument(
        "--repo-path",
        default=None,
        help=(
            "Optional caller-approved local git repository path. Planning keeps "
            "this as a dry-run and never records the path."
        ),
    )
    workflow_parser.add_argument(
        "--base-branch",
        default="main",
        help="Approved local base branch for the eventual issue branch.",
    )
    workflow_parser.add_argument(
        "--issue-branch",
        default=None,
        help="Optional issue branch for the eventual caller-repo execution.",
    )
    workflow_parser.add_argument(
        "--validation-label",
        default="caller-declared validation",
        help="Public-safe validation label stored in the workflow plan.",
    )
    workflow_parser.add_argument(
        "--repository-context-json",
        default=None,
        help=(
            "Optional issue_fix_repository_context_input_v0 JSON path, or '-' for "
            "stdin. Only compact source refs, trust, freshness, and coverage are kept."
        ),
    )
    workflow_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the workflow plan.",
    )
    feasibility_parser = issue_fix_sub.add_parser(
        "feasibility",
        help=(
            "Select exactly one fix_pr, comment_only, or triage_only route "
            "from compact public-safe agent observations."
        ),
    )
    add_subcommand_format(feasibility_parser)
    feasibility_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the issue.",
    )
    feasibility_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue reference label.",
    )
    feasibility_parser.add_argument(
        "--url",
        default=None,
        help="Optional https://github.com/owner/repo/issues/123 URL.",
    )
    feasibility_parser.add_argument(
        "--reproduction-status",
        required=True,
        choices=("confirmed", "planned", "missing", "blocked"),
        help="Compact agent observation of reproduction readiness.",
    )
    feasibility_parser.add_argument(
        "--scope-class",
        required=True,
        choices=("bounded", "uncertain", "oversized"),
        help="Compact agent observation of expected change scope.",
    )
    feasibility_parser.add_argument(
        "--reproduction-label",
        default=None,
        help="Compact public-safe repro or repro-plan label; never raw logs.",
    )
    feasibility_parser.add_argument(
        "--validation-label",
        default=None,
        help="Compact public-safe validation surface label.",
    )
    feasibility_parser.add_argument(
        "--comment-value",
        default="none",
        choices=("none", "clarification", "diagnosis"),
        help="Whether a maintainer-facing comment would add public value.",
    )
    feasibility_parser.add_argument(
        "--repository-context-json",
        default=None,
        help=(
            "Optional issue_fix_repository_context_input_v0 JSON path, or '-' for "
            "stdin. The compact projection is persisted with feasibility domain state."
        ),
    )
    feasibility_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the feasibility decision.",
    )
    feasibility_parser.add_argument(
        "--goal-id",
        default=None,
        help="Goal id used for the default issue_fix feasibility ledger path.",
    )
    feasibility_parser.add_argument(
        "--project",
        default=".",
        help="Project root for the default issue_fix feasibility ledger path.",
    )
    feasibility_parser.add_argument(
        "--ledger-path",
        default=None,
        help="Optional local JSONL ledger path. Overrides the default path.",
    )
    feasibility_parser.add_argument(
        "--no-write-domain-state",
        action="store_true",
        help=(
            "Keep feasibility preview-only even when --goal-id or --ledger-path "
            "is present."
        ),
    )
    pr_lifecycle_parser = issue_fix_sub.add_parser(
        "pr-lifecycle",
        help=(
            "Project a public PR lifecycle observation into a successor, "
            "monitor-continuation, user-gate, or no-follow-up transition."
        ),
    )
    add_subcommand_format(pr_lifecycle_parser)
    pr_lifecycle_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the PR metadata.",
    )
    pr_lifecycle_parser.add_argument(
        "--pr-ref",
        default="pull_123_public_metadata_fixture",
        help="Public-safe PR reference label.",
    )
    pr_lifecycle_parser.add_argument(
        "--url",
        default=None,
        help="Optional https://github.com/owner/repo/pull/123 URL.",
    )
    pr_lifecycle_parser.add_argument(
        "--metadata-json",
        default=None,
        help=(
            "Path to mocked gh pr view JSON metadata, or '-' for stdin. "
            "Bodies, comments, raw logs, and provider responses stay out."
        ),
    )
    pr_lifecycle_parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help=(
            "Explicitly fetch public GitHub PR state with gh pr view. "
            "Only compact lifecycle fields are captured."
        ),
    )
    pr_lifecycle_parser.add_argument(
        "--fetch-timeout-seconds",
        type=int,
        default=10,
        help="Timeout for --fetch-metadata.",
    )
    pr_lifecycle_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the lifecycle projection.",
    )
    pr_lifecycle_parser.add_argument(
        "--goal-id",
        default=None,
        help="Goal id used for the default issue_fix domain-state ledger path.",
    )
    pr_lifecycle_parser.add_argument(
        "--project",
        default=".",
        help="Project root for the default issue_fix domain-state ledger path.",
    )
    pr_lifecycle_parser.add_argument(
        "--ledger-path",
        default=None,
        help="Optional local JSONL ledger path. Overrides the default domain-state path.",
    )
    pr_lifecycle_parser.add_argument(
        "--no-write-domain-state",
        action="store_true",
        help=(
            "Keep the PR lifecycle command preview-only even when --goal-id or "
            "--ledger-path is present."
        ),
    )
    outcome_parser = issue_fix_sub.add_parser(
        "outcome",
        help=(
            "Compose one public-safe issue-fix status/output projection from "
            "existing feasibility and optional PR lifecycle state."
        ),
    )
    add_subcommand_format(outcome_parser)
    outcome_parser.add_argument("--goal-id", required=True)
    outcome_parser.add_argument("--project", default=".")
    outcome_parser.add_argument("--repo", required=True)
    outcome_parser.add_argument("--issue-ref", required=True)
    outcome_parser.add_argument(
        "--pr-ref",
        help="Optional PR ref linked to this issue, such as pull_456.",
    )
    outcome_parser.add_argument(
        "--feasibility-json",
        help="Optional issue_fix_feasibility_v0 JSON object; defaults to domain state.",
    )
    outcome_parser.add_argument(
        "--pr-lifecycle-json",
        help=(
            "Optional issue_fix_pr_lifecycle_monitor_v0 JSON object; defaults "
            "to domain state when --pr-ref is present."
        ),
    )
    outcome_parser.add_argument(
        "--delivery-evidence-json",
        help=(
            "Optional issue_fix_delivery_evidence_input_v0 JSON with explicit "
            "validation status, repo-relative changed files, commit ref, outputs, and risks."
        ),
    )
    outcome_parser.add_argument(
        "--agent-id",
        help="Optional registered agent id projected as the case owner.",
    )
    outcome_parser.add_argument(
        "--generated-at",
        default="2026-07-10T00:00:00Z",
        help="Public-safe generated_at timestamp for the read model.",
    )
    reviewer_parser = issue_fix_sub.add_parser(
        "reviewer-plan",
        help=(
            "Recommend reviewers from caller-approved repository ownership "
            "evidence without requesting external review."
        ),
    )
    add_subcommand_format(reviewer_parser)
    reviewer_parser.add_argument(
        "--repo-path",
        required=True,
        help=(
            "Caller-approved local git repository. The public packet never "
            "records this path."
        ),
    )
    reviewer_parser.add_argument(
        "--repo",
        default="approved_local_repo",
        help="Public-safe repository label stored in the recommendation packet.",
    )
    reviewer_parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help=(
            "Repo-relative changed file. Repeat for multiple files. When omitted "
            "with --execute, derive files from --base-ref...HEAD."
        ),
    )
    reviewer_parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Base git ref used to derive changed files when none are explicit.",
    )
    reviewer_parser.add_argument(
        "--history-limit",
        type=int,
        default=40,
        help="Maximum changed-path git history rows to inspect per file.",
    )
    reviewer_parser.add_argument(
        "--max-candidates",
        type=int,
        default=5,
        help="Maximum ranked reviewer candidates to return.",
    )
    reviewer_parser.add_argument(
        "--exclude-reviewer",
        action="append",
        default=[],
        help=(
            "GitHub handle to exclude, normally the PR author or unavailable "
            "reviewer. Repeat for multiple handles."
        ),
    )
    reviewer_parser.add_argument(
        "--exclude-author-name",
        action="append",
        default=[],
        help=(
            "Git author display-name alias to exclude when it cannot be resolved "
            "to the PR author handle. Repeat for multiple aliases."
        ),
    )
    reviewer_parser.add_argument(
        "--identity-map-json",
        help=(
            "Optional public-safe JSON object mapping verified git display names "
            "to GitHub handles; raw mapping is not copied into output."
        ),
    )
    reviewer_parser.add_argument(
        "--reviewer-sources-json",
        help=(
            "Optional public-safe issue_fix_reviewer_sources_input_v0 JSON with "
            "repository-declared path routes, primary/fallback handles, trust, "
            "freshness, observation time, and source references."
        ),
    )
    reviewer_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Inspect only the caller-approved local repository. This still "
            "does not request review or perform any external write."
        ),
    )
    reviewer_parser.add_argument(
        "--generated-at",
        default="2026-07-10T00:00:00Z",
        help="Public-safe generated_at timestamp for the recommendation packet.",
    )
    reviewer_request_parser = issue_fix_sub.add_parser(
        "reviewer-request",
        help=(
            "Select the top requestable non-author reviewer and, with explicit "
            "external-write authority, verify a formal request or its "
            "permission-only comment fallback."
        ),
    )
    add_subcommand_format(reviewer_request_parser)
    reviewer_request_parser.add_argument(
        "--url",
        required=True,
        help="Canonical public GitHub pull request URL.",
    )
    reviewer_request_parser.add_argument(
        "--repo-path",
        required=True,
        help="Caller-approved local git repository; never copied into output.",
    )
    reviewer_request_parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Repo-relative changed file; repeat or derive from --base-ref...HEAD.",
    )
    reviewer_request_parser.add_argument("--base-ref", default="origin/main")
    reviewer_request_parser.add_argument("--history-limit", type=int, default=40)
    reviewer_request_parser.add_argument("--max-candidates", type=int, default=5)
    reviewer_request_parser.add_argument(
        "--max-reviewers",
        type=int,
        default=1,
        help="Bounded reviewer request count; default one, maximum three.",
    )
    reviewer_request_parser.add_argument(
        "--exclude-reviewer", action="append", default=[]
    )
    reviewer_request_parser.add_argument(
        "--exclude-author-name", action="append", default=[]
    )
    reviewer_request_parser.add_argument(
        "--identity-map-json",
        help=(
            "Optional public-safe JSON object mapping human-verified git display "
            "names to GitHub handles."
        ),
    )
    reviewer_request_parser.add_argument(
        "--reviewer-sources-json",
        help=(
            "Optional public-safe issue_fix_reviewer_sources_input_v0 JSON; "
            "the selected candidate still requires live author exclusion and "
            "external-write authority. Source freshness must include observation time."
        ),
    )
    reviewer_request_parser.add_argument(
        "--metadata-json",
        help=(
            "Optional compact PR metadata JSON for a no-write preview. Live execute "
            "mode fetches and verifies GitHub state instead."
        ),
    )
    reviewer_request_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Assert external-review-request authority, try formal GitHub review, "
            "fall back to one reviewer-tagging comment only on permission denial, "
            "and verify the result."
        ),
    )
    reviewer_request_parser.add_argument(
        "--generated-at",
        default="2026-07-10T00:00:00Z",
        help="Public-safe generated_at timestamp for the request packet.",
    )
    acceptance_parser = issue_fix_sub.add_parser(
        "acceptance-fixture",
        help=(
            "Run a deterministic fix loop: failing repro, minimal patch, "
            "focused validation, and PR-review-ready artifact."
        ),
    )
    add_subcommand_format(acceptance_parser)
    acceptance_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the issue metadata fixture.",
    )
    acceptance_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue or PR reference label for the fixture.",
    )
    acceptance_parser.add_argument(
        "--url",
        default=None,
        help="Optional public GitHub issue or PR URL for metadata parsing.",
    )
    acceptance_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the fixture artifact.",
    )
    branch_parser = issue_fix_sub.add_parser(
        "repo-branch-fixture",
        help=(
            "Run the fix loop through a temporary git repo issue branch: "
            "branch, repro, patch, validation, and PR evidence."
        ),
    )
    add_subcommand_format(branch_parser)
    branch_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the issue metadata fixture.",
    )
    branch_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue or PR reference label for the fixture.",
    )
    branch_parser.add_argument(
        "--url",
        default=None,
        help="Optional public GitHub issue or PR URL for metadata parsing.",
    )
    branch_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the fixture artifact.",
    )
    caller_branch_parser = issue_fix_sub.add_parser(
        "caller-repo-branch",
        help=(
            "Prepare or execute an explicitly approved local repo issue branch "
            "workflow without external comments, PR creation, or merge."
        ),
    )
    add_subcommand_format(caller_branch_parser)
    caller_branch_parser.add_argument(
        "--repo-path",
        required=True,
        help=(
            "Caller-approved local git repository path. The public artifact records "
            "only a repo label, never this path."
        ),
    )
    caller_branch_parser.add_argument(
        "--repo",
        default="approved_local_repo",
        help="Public-safe repository label when no URL-derived repo is provided.",
    )
    caller_branch_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata",
        help="Public-safe issue or PR reference label.",
    )
    caller_branch_parser.add_argument(
        "--url",
        default=None,
        help="Optional public GitHub issue or PR URL used only for compact metadata.",
    )
    caller_branch_parser.add_argument(
        "--base-branch",
        default="main",
        help="Approved local base branch used when creating a new issue branch.",
    )
    caller_branch_parser.add_argument(
        "--issue-branch",
        default=None,
        help="Optional issue branch to create or claim. Defaults to codex/<issue>-fix.",
    )
    caller_branch_parser.add_argument(
        "--validation-command",
        default=None,
        help="Caller-declared validation command. Required with --execute.",
    )
    caller_branch_parser.add_argument(
        "--validation-label",
        default="caller-declared validation",
        help="Public-safe validation label stored in the artifact instead of raw command text.",
    )
    caller_branch_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Validation timeout in seconds.",
    )
    caller_branch_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually inspect the approved repo, create or claim the issue branch, "
            "and run the caller-declared validation."
        ),
    )
    caller_branch_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the artifact.",
    )


def handle_issue_fix_command(
    args: argparse.Namespace,
    *,
    registry_path: Path | None = None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.issue_fix_command == "workflow-plan":
            if args.fetch_metadata and args.metadata_json:
                raise ValueError("--fetch-metadata cannot be combined with --metadata-json")
            if args.metadata_json == "-" and args.repository_context_json == "-":
                raise ValueError("only one JSON input may read from stdin")
            payload = build_issue_fix_workflow_plan_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                provider_payload=_load_json_object(args.metadata_json)
                if args.metadata_json
                else None,
                fetch_metadata=args.fetch_metadata,
                fetch_timeout_seconds=args.fetch_timeout_seconds,
                repo_path=args.repo_path,
                base_branch=args.base_branch,
                issue_branch=args.issue_branch,
                validation_label=args.validation_label,
                repository_context_input=(
                    _load_json_object(args.repository_context_json)
                    if args.repository_context_json
                    else None
                ),
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_workflow_plan_markdown
        elif args.issue_fix_command == "feasibility":
            boundary_authority_scopes, boundary_authority_resolved = (
                _goal_boundary_authority_projection(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                )
            )
            payload = build_issue_fix_feasibility_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                reproduction_status=args.reproduction_status,
                scope_class=args.scope_class,
                reproduction_label=args.reproduction_label,
                validation_label=args.validation_label,
                comment_value=args.comment_value,
                repository_context_input=(
                    _load_json_object(args.repository_context_json)
                    if args.repository_context_json
                    else None
                ),
                boundary_authority_scopes=boundary_authority_scopes,
                boundary_authority_resolved=boundary_authority_resolved,
                generated_at=args.generated_at,
            )
            should_write_domain_state = bool(
                not args.no_write_domain_state and (args.goal_id or args.ledger_path)
            )
            if should_write_domain_state:
                ledger_path = (
                    Path(args.ledger_path).expanduser()
                    if args.ledger_path
                    else default_issue_fix_feasibility_ledger_path(
                        project=args.project,
                        goal_id=args.goal_id,
                    )
                )
                upsert_issue_fix_feasibility_ledger_jsonl(
                    ledger_path,
                    payload,
                )
            else:
                domain_state = payload.get("domain_state_projection")
                if isinstance(domain_state, dict) and not args.no_write_domain_state:
                    domain_state["write_skipped_reason"] = (
                        "goal_id_or_ledger_path_missing"
                    )
            renderer = render_issue_fix_feasibility_markdown
        elif args.issue_fix_command == "pr-lifecycle":
            if args.fetch_metadata and args.metadata_json:
                raise ValueError("--fetch-metadata cannot be combined with --metadata-json")
            payload = build_issue_fix_pr_lifecycle_monitor_packet(
                repo=args.repo,
                pr_ref=args.pr_ref,
                url=args.url,
                provider_payload=_load_json_object(args.metadata_json)
                if args.metadata_json
                else None,
                fetch_metadata=args.fetch_metadata,
                fetch_timeout_seconds=args.fetch_timeout_seconds,
                generated_at=args.generated_at,
            )
            should_write_domain_state = bool(
                not args.no_write_domain_state and (args.goal_id or args.ledger_path)
            )
            if should_write_domain_state:
                ledger_path = (
                    Path(args.ledger_path).expanduser()
                    if args.ledger_path
                    else default_issue_fix_domain_state_ledger_path(
                        project=args.project,
                        goal_id=args.goal_id,
                    )
                )
                upsert_issue_fix_pr_lifecycle_ledger_jsonl(
                    ledger_path,
                    payload,
                )
            else:
                domain_state = payload.get("domain_state_projection")
                if isinstance(domain_state, dict) and not args.no_write_domain_state:
                    domain_state["write_skipped_reason"] = "goal_id_or_ledger_path_missing"
            renderer = render_issue_fix_pr_lifecycle_monitor_markdown
        elif args.issue_fix_command == "outcome":
            stdin_input_count = sum(
                value == "-"
                for value in (
                    args.feasibility_json,
                    args.pr_lifecycle_json,
                    args.delivery_evidence_json,
                )
            )
            if stdin_input_count > 1:
                raise ValueError("only one outcome JSON input may read from stdin")
            project = Path(args.project).expanduser()
            feasibility_packet = (
                _load_json_object(args.feasibility_json)
                if args.feasibility_json
                else _load_jsonl_row(
                    default_issue_fix_feasibility_ledger_path(
                        project=project,
                        goal_id=args.goal_id,
                    ),
                    repo=args.repo,
                    ref_field="issue_ref",
                    ref_value=args.issue_ref,
                )
            )
            feasibility_observation = feasibility_packet.get("observation")
            if not isinstance(feasibility_observation, dict) or (
                str(feasibility_observation.get("repo") or "").strip() != args.repo
                or str(feasibility_observation.get("issue_ref") or "").strip()
                != args.issue_ref
            ):
                raise ValueError(
                    "--repo/--issue-ref must match the selected feasibility packet"
                )
            pr_lifecycle_packet = None
            if args.pr_lifecycle_json:
                pr_lifecycle_packet = _load_json_object(args.pr_lifecycle_json)
            elif args.pr_ref:
                pr_lifecycle_packet = _load_jsonl_row(
                    default_issue_fix_domain_state_ledger_path(
                        project=project,
                        goal_id=args.goal_id,
                    ),
                    repo=args.repo,
                    ref_field="pr_ref",
                    ref_value=args.pr_ref,
                )
            if pr_lifecycle_packet is not None and args.pr_ref:
                lifecycle_observation = pr_lifecycle_packet.get("observation")
                if not isinstance(lifecycle_observation, dict) or str(
                    lifecycle_observation.get("pr_ref") or ""
                ).strip() != args.pr_ref:
                    raise ValueError(
                        "--pr-ref must match the selected PR lifecycle packet"
                    )
            payload = build_issue_fix_outcome_projection(
                goal_id=args.goal_id,
                feasibility_packet=feasibility_packet,
                pr_lifecycle_packet=pr_lifecycle_packet,
                delivery_evidence_input=(
                    _load_json_object(args.delivery_evidence_json)
                    if args.delivery_evidence_json
                    else None
                ),
                agent_id=args.agent_id,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_outcome_projection_markdown
        elif args.issue_fix_command == "reviewer-plan":
            payload = build_issue_fix_reviewer_recommendation_packet(
                repo_path=args.repo_path,
                repo=args.repo,
                changed_files=args.changed_file,
                base_ref=args.base_ref,
                history_limit=args.history_limit,
                max_candidates=args.max_candidates,
                exclude_reviewers=args.exclude_reviewer,
                exclude_author_names=args.exclude_author_name,
                resolved_identities=(
                    _load_json_object(args.identity_map_json)
                    if args.identity_map_json
                    else None
                ),
                reviewer_sources_input=(
                    _load_json_object(args.reviewer_sources_json)
                    if args.reviewer_sources_json
                    else None
                ),
                execute=args.execute,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_reviewer_recommendation_markdown
        elif args.issue_fix_command == "reviewer-request":
            payload = build_issue_fix_reviewer_request_packet(
                repo_path=args.repo_path,
                url=args.url,
                changed_files=args.changed_file,
                base_ref=args.base_ref,
                history_limit=args.history_limit,
                max_candidates=args.max_candidates,
                max_reviewers=args.max_reviewers,
                exclude_reviewers=args.exclude_reviewer,
                exclude_author_names=args.exclude_author_name,
                resolved_identities=(
                    _load_json_object(args.identity_map_json)
                    if args.identity_map_json
                    else None
                ),
                reviewer_sources_input=(
                    _load_json_object(args.reviewer_sources_json)
                    if args.reviewer_sources_json
                    else None
                ),
                provider_payload=(
                    _load_json_object(args.metadata_json)
                    if args.metadata_json
                    else None
                ),
                execute=args.execute,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_reviewer_request_markdown
        elif args.issue_fix_command == "acceptance-fixture":
            payload = build_issue_fix_acceptance_fixture_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_acceptance_loop_markdown
        elif args.issue_fix_command == "repo-branch-fixture":
            payload = build_issue_fix_repo_branch_fixture_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_acceptance_loop_markdown
        elif args.issue_fix_command == "caller-repo-branch":
            payload = build_issue_fix_caller_repo_branch_packet(
                repo_path=args.repo_path,
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                base_branch=args.base_branch,
                issue_branch=args.issue_branch,
                validation_command=args.validation_command,
                validation_label=args.validation_label,
                execute=args.execute,
                timeout_seconds=args.timeout_seconds,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_acceptance_loop_markdown
        else:
            raise ValueError(
                "issue-fix requires `workflow-plan`, `feasibility`, "
                "`acceptance-fixture`, `pr-lifecycle`, `outcome`, `reviewer-plan`, "
                "`reviewer-request`, "
                "`repo-branch-fixture`, or `caller-repo-branch`"
            )
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "issue-fix",
            "error": str(exc),
        }
        renderer = (
            render_issue_fix_workflow_plan_markdown
            if getattr(args, "issue_fix_command", None) == "workflow-plan"
            else render_issue_fix_feasibility_markdown
            if getattr(args, "issue_fix_command", None) == "feasibility"
            else render_issue_fix_pr_lifecycle_monitor_markdown
            if getattr(args, "issue_fix_command", None) == "pr-lifecycle"
            else render_issue_fix_outcome_projection_markdown
            if getattr(args, "issue_fix_command", None) == "outcome"
            else render_issue_fix_reviewer_recommendation_markdown
            if getattr(args, "issue_fix_command", None) == "reviewer-plan"
            else render_issue_fix_reviewer_request_markdown
            if getattr(args, "issue_fix_command", None) == "reviewer-request"
            else render_issue_fix_acceptance_loop_markdown
        )
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
