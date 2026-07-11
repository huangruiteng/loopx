from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...agent_registry import load_goal_from_registry
from ...boundary_authority import checkpointed_boundary_authority_summary
from ...control_plane.runtime.time import now_utc_iso
from ...domain_packs.issue_fix import (
    default_issue_fix_domain_state_ledger_path,
    default_issue_fix_feasibility_ledger_path,
    persist_issue_fix_reviewer_notification_receipts,
    upsert_issue_fix_feasibility_ledger_jsonl,
    upsert_issue_fix_pr_lifecycle_ledger_jsonl,
)
from ...todos import add_goal_todo
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
    compact_issue_fix_delivery_evidence,
    render_issue_fix_outcome_projection_markdown,
)
from .metadata_preview import normalise_github_issue_reference
from .pr_lifecycle import (
    build_issue_fix_pr_lifecycle_monitor_packet,
    render_issue_fix_pr_lifecycle_monitor_markdown,
    validate_issue_fix_pr_lifecycle_monitor_packet,
)
from .reviewer_recommendation import (
    build_issue_fix_reviewer_recommendation_packet,
    render_issue_fix_reviewer_recommendation_markdown,
)
from .reviewer_request import (
    build_issue_fix_reviewer_request_packet,
    render_issue_fix_reviewer_request_markdown,
)
from .reviewer_notification import (
    load_goal_reviewer_notification_sinks_input,
    reviewer_notification_receipts_from_state,
    with_reviewer_notification_receipts,
)
from .repository_memory import SUPPORT_ASPECTS
from .repository_memory_provider import (
    default_repository_memory_provider_config_path,
    render_issue_fix_repository_memory_sync_markdown,
    retrieve_issue_fix_repository_memory,
    sync_issue_fix_repository_memory,
    write_issue_fix_validated_outcome_memory,
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


_MAX_INLINE_JSON_CHARS = 1_048_576


def _load_json_object(input_text: str) -> dict[str, Any]:
    stripped = input_text.lstrip()
    if input_text == "-":
        source = "stdin"
        raw = sys.stdin.read()
    elif stripped.startswith(("{", "[")):
        source = "inline"
        raw = input_text
    else:
        source = "file"
        try:
            raw = Path(input_text).expanduser().read_text(encoding="utf-8")
        except (OSError, RuntimeError):
            raise ValueError("could not read JSON input file") from None
    if source == "inline" and len(raw) > _MAX_INLINE_JSON_CHARS:
        raise ValueError("inline JSON input exceeds the 1 MiB limit")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("JSON input is invalid") from None
    if not isinstance(payload, dict):
        raise ValueError("JSON input must contain an object")
    return payload


def _configured_repository_memory_input(
    *,
    provider_path: str | None,
    raw_memory_path: str | None,
    repo_path: str | None,
    repository_context_input: dict[str, Any] | None,
    repo: str,
    issue_ref: str,
    query: str | None,
    supports: list[str],
    validation_label: str | None,
    observed_at: str,
) -> dict[str, Any] | None:
    if raw_memory_path and provider_path:
        raise ValueError(
            "--repository-memory-json cannot be combined with a configured provider"
        )
    if raw_memory_path:
        return _load_json_object(raw_memory_path)
    if not provider_path:
        return None
    if not repo_path or not repository_context_input:
        return None
    revision = str(repository_context_input.get("repository_revision") or "").strip()
    if not revision:
        return None
    retrieval_query = query or " ".join(
        value
        for value in (
            repo,
            issue_ref,
            validation_label or "repository architecture reproduction validation",
        )
        if value
    )
    query_summary = (
        query
        or f"Public repository context for {repo} {issue_ref} before patch planning."
    )
    result = retrieve_issue_fix_repository_memory(
        config=_load_json_object(provider_path),
        repo_path=repo_path,
        repository_revision=revision,
        query=retrieval_query,
        query_summary=query_summary,
        supports=(
            supports or ["architecture", "change_scope", "reproduction", "validation"]
        ),
        observed_at=observed_at,
    )
    return result["memory_input"]


def _add_repository_memory_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repository-memory-provider-json",
        default=None,
        help=(
            "Optional local-private issue_fix_repository_memory_provider_config_v0. "
            "Defaults to LOOPX_ISSUE_FIX_REPOSITORY_MEMORY_PROVIDER_CONFIG. "
            "The path, provider command, credentials, and raw payloads are never kept."
        ),
    )
    parser.add_argument(
        "--repository-memory-query",
        default=None,
        help=(
            "Optional compact public query for configured provider search/read. "
            "A bounded issue/ref/validation query is derived when omitted."
        ),
    )
    parser.add_argument(
        "--repository-memory-support",
        action="append",
        default=[],
        choices=sorted(SUPPORT_ASPECTS),
        help="Repository aspect supported by retrieved context. Repeat as needed.",
    )


def _add_generated_at_arg(
    parser: argparse.ArgumentParser,
    *,
    artifact: str,
) -> None:
    parser.add_argument(
        "--generated-at",
        default=None,
        help=(
            f"Public-safe generated_at timestamp for {artifact}; "
            "defaults to current UTC invocation time."
        ),
    )


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


def _load_goal_for_project(
    *,
    registry_path: Path | None,
    goal_id: str,
    project: str | Path,
) -> tuple[dict[str, Any], Path]:
    """Resolve a connected goal from the active or explicit project registry."""

    requested_project = Path(project).expanduser().resolve()
    project_registry = requested_project / ".loopx" / "registry.json"
    candidates = [
        path for path in (registry_path, project_registry) if path is not None
    ]
    mismatched_goal = False
    for candidate in dict.fromkeys(candidates):
        goal = load_goal_from_registry(candidate, goal_id)
        if not isinstance(goal, dict):
            continue
        goal_repo = str(goal.get("repo") or "").strip()
        if not goal_repo:
            raise ValueError(
                "connected goal repository is required for goal-scoped "
                "reviewer notification"
            )
        if Path(goal_repo).expanduser().resolve() == requested_project:
            return goal, requested_project
        mismatched_goal = True

    if mismatched_goal:
        raise ValueError(
            "--project must match the connected goal repository for "
            "goal-scoped reviewer notification"
        )
    raise ValueError(
        "goal-scoped reviewer notification goal was not found in the active "
        "or project-local registry"
    )


def _materialize_goal_reviewer_notification_lifecycle(
    *,
    ledger_path: str | Path,
    url: str,
    generated_at: str | None = None,
    provider_payload: dict[str, Any] | None = None,
    fetch_metadata: bool = False,
) -> dict[str, Any]:
    """Create the compact PR lifecycle row required for receipt persistence."""

    packet = build_issue_fix_pr_lifecycle_monitor_packet(
        url=url,
        provider_payload=provider_payload,
        fetch_metadata=fetch_metadata,
        generated_at=generated_at,
    )
    upsert_issue_fix_pr_lifecycle_ledger_jsonl(ledger_path, packet)
    return packet


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
    memory_sync_parser = issue_fix_sub.add_parser(
        "repository-memory-sync",
        help=(
            "Plan or explicitly execute a bounded revision-scoped public resource "
            "sync through the reusable context-provider module."
        ),
    )
    add_subcommand_format(memory_sync_parser)
    memory_sync_parser.add_argument("--repo-path", required=True)
    memory_sync_parser.add_argument("--repository-context-json", required=True)
    memory_sync_parser.add_argument(
        "--repository-memory-provider-json",
        default=None,
        help=(
            "Local-private provider config; defaults to "
            "LOOPX_ISSUE_FIX_REPOSITORY_MEMORY_PROVIDER_CONFIG."
        ),
    )
    memory_sync_parser.add_argument(
        "--resource-reference",
        action="append",
        default=[],
        required=True,
        help="Repo-relative public file to index. Repeat up to the bounded cap.",
    )
    memory_sync_parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the provider resource write. Without this flag, return a plan.",
    )
    _add_generated_at_arg(memory_sync_parser, artifact="the resource sync")
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
        "--repository-memory-json",
        default=None,
        help=(
            "Optional issue_fix_repository_memory_read_result_v0 JSON path, or '-' "
            "for stdin. The host must perform explicit public-namespace search/read; "
            "LoopX keeps only compact advisory refs and checkout verification."
        ),
    )
    _add_repository_memory_provider_args(workflow_parser)
    _add_generated_at_arg(workflow_parser, artifact="the workflow plan")
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
        "--repository-memory-json",
        default=None,
        help=(
            "Optional issue_fix_repository_memory_read_result_v0 JSON path, or '-' "
            "for stdin. Provider failures stay fail-open and no writeback is allowed."
        ),
    )
    feasibility_parser.add_argument(
        "--repo-path",
        default=None,
        help=(
            "Optional caller-approved current checkout used only to verify provider "
            "content. The path is never retained."
        ),
    )
    _add_repository_memory_provider_args(feasibility_parser)
    _add_generated_at_arg(feasibility_parser, artifact="the feasibility decision")
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
        "--issue-ref",
        default=None,
        help=(
            "Optional public-safe issue reference linked to this PR. Persisting "
            "the explicit link lets default Kanban sync compose the issue outcome "
            "without guessing from titles or branch names. Numeric aliases such "
            "as #123 and issue_123 are stored as issues_123."
        ),
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
        "--maintainer-correction-json",
        default=None,
        help=(
            "Optional issue_fix_maintainer_correction_input_v0 JSON object. "
            "It contains only a compact public correction, source reference, "
            "verification plan/update path, ambiguity question, or missing scopes."
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
    _add_generated_at_arg(pr_lifecycle_parser, artifact="the lifecycle projection")
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
    pr_lifecycle_parser.add_argument(
        "--execute-transition",
        action="store_true",
        help=(
            "Write the correction transition into the existing LoopX todo state. "
            "Requires --goal-id, --claimed-by, --maintainer-correction-json, and a registry."
        ),
    )
    pr_lifecycle_parser.add_argument(
        "--claimed-by",
        default=None,
        help=(
            "Registered agent that claims an actionable patch successor or is blocked "
            "by the generated concrete user gate."
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
        "--write-delivery-evidence",
        action="store_true",
        help=(
            "Validate and write compact delivery evidence into the selected "
            "existing feasibility row so default outcome and Kanban sync retain it."
        ),
    )
    outcome_parser.add_argument(
        "--repository-memory-provider-json",
        default=None,
        help=(
            "Local-private issue_fix_repository_memory_provider_config_v0 used "
            "only when --write-repository-memory is explicit. Defaults to "
            "LOOPX_ISSUE_FIX_REPOSITORY_MEMORY_PROVIDER_CONFIG."
        ),
    )
    outcome_parser.add_argument(
        "--write-repository-memory",
        action="store_true",
        help=(
            "After passed validation and completed delivery, write one distilled "
            "public outcome through an owner-enabled, revision-scoped provider. "
            "No transcript or tool-result capture is performed."
        ),
    )
    outcome_parser.add_argument(
        "--repo-path",
        default=None,
        help=(
            "Caller-approved git checkout used only to prove that delivery commit_ref "
            "is contained in the pinned repository revision before memory writeback. "
            "The path and raw git output are never recorded."
        ),
    )
    outcome_parser.add_argument(
        "--agent-id",
        help="Optional registered agent id projected as the case owner.",
    )
    _add_generated_at_arg(outcome_parser, artifact="the read model")
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
    _add_generated_at_arg(reviewer_parser, artifact="the recommendation packet")
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
            "Optional compact PR metadata as an inline JSON object, file path, or "
            "'-' for stdin in a no-write preview. Live execute mode fetches and "
            "verifies GitHub state instead."
        ),
    )
    reviewer_request_parser.add_argument(
        "--notification-sinks-json",
        help=(
            "Optional local-private issue_fix_reviewer_notification_sinks_input_v0 "
            "JSON. Destination, bot profile, and member IDs are consumed locally "
            "and never copied into the public result."
        ),
    )
    reviewer_request_parser.add_argument(
        "--goal-id",
        help=(
            "Optional connected goal whose registered local-private default sink "
            "and existing PR lifecycle receipts should be reused."
        ),
    )
    reviewer_request_parser.add_argument(
        "--project",
        default=".",
        help="Project root used for goal-default sink config and issue_fix domain state.",
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
    _add_generated_at_arg(reviewer_request_parser, artifact="the request packet")
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
    _add_generated_at_arg(acceptance_parser, artifact="the fixture artifact")
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
    _add_generated_at_arg(branch_parser, artifact="the fixture artifact")
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
    _add_generated_at_arg(caller_branch_parser, artifact="the artifact")


def handle_issue_fix_command(
    args: argparse.Namespace,
    *,
    registry_path: Path | None = None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        generated_at = str(args.generated_at or now_utc_iso()).strip()
        if args.issue_fix_command == "repository-memory-sync":
            provider_path = (
                args.repository_memory_provider_json
                or default_repository_memory_provider_config_path()
            )
            if not provider_path:
                raise ValueError("repository memory provider config is required")
            if provider_path == "-" and args.repository_context_json == "-":
                raise ValueError("only one JSON input may read from stdin")
            repository_context_input = _load_json_object(args.repository_context_json)
            revision = str(
                repository_context_input.get("repository_revision") or ""
            ).strip()
            if not revision:
                raise ValueError("repository context must pin repository_revision")
            payload = sync_issue_fix_repository_memory(
                config=_load_json_object(provider_path),
                repo_path=args.repo_path,
                repository_revision=revision,
                references=args.resource_reference,
                observed_at=generated_at,
                execute=args.execute,
            )
            renderer = render_issue_fix_repository_memory_sync_markdown
        elif args.issue_fix_command == "workflow-plan":
            if args.fetch_metadata and args.metadata_json:
                raise ValueError("--fetch-metadata cannot be combined with --metadata-json")
            provider_path = args.repository_memory_provider_json or (
                None
                if args.repository_memory_json
                else default_repository_memory_provider_config_path()
            )
            stdin_inputs = [
                value
                for value in (
                    args.metadata_json,
                    args.repository_context_json,
                    args.repository_memory_json,
                    provider_path,
                )
                if value == "-"
            ]
            if len(stdin_inputs) > 1:
                raise ValueError("only one JSON input may read from stdin")
            repository_context_input = (
                _load_json_object(args.repository_context_json)
                if args.repository_context_json
                else None
            )
            repository_memory_input = _configured_repository_memory_input(
                provider_path=provider_path,
                raw_memory_path=args.repository_memory_json,
                repo_path=args.repo_path,
                repository_context_input=repository_context_input,
                repo=args.repo,
                issue_ref=args.issue_ref,
                query=args.repository_memory_query,
                supports=args.repository_memory_support,
                validation_label=args.validation_label,
                observed_at=generated_at,
            )
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
                repository_context_input=repository_context_input,
                repository_memory_input=repository_memory_input,
                generated_at=generated_at,
            )
            renderer = render_issue_fix_workflow_plan_markdown
        elif args.issue_fix_command == "feasibility":
            provider_path = args.repository_memory_provider_json or (
                None
                if args.repository_memory_json
                else default_repository_memory_provider_config_path()
            )
            if (
                args.repository_context_json == "-"
                and args.repository_memory_json == "-"
            ):
                raise ValueError("only one JSON input may read from stdin")
            if provider_path == "-" and (
                args.repository_context_json == "-"
                or args.repository_memory_json == "-"
            ):
                raise ValueError("only one JSON input may read from stdin")
            repository_context_input = (
                _load_json_object(args.repository_context_json)
                if args.repository_context_json
                else None
            )
            repository_memory_input = _configured_repository_memory_input(
                provider_path=provider_path,
                raw_memory_path=args.repository_memory_json,
                repo_path=args.repo_path,
                repository_context_input=repository_context_input,
                repo=args.repo,
                issue_ref=args.issue_ref,
                query=args.repository_memory_query,
                supports=args.repository_memory_support,
                validation_label=args.validation_label,
                observed_at=generated_at,
            )
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
                repository_context_input=repository_context_input,
                repository_memory_input=repository_memory_input,
                boundary_authority_scopes=boundary_authority_scopes,
                boundary_authority_resolved=boundary_authority_resolved,
                generated_at=generated_at,
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
            if args.execute_transition and not args.maintainer_correction_json:
                raise ValueError(
                    "--execute-transition requires --maintainer-correction-json"
                )
            payload = build_issue_fix_pr_lifecycle_monitor_packet(
                repo=args.repo,
                pr_ref=args.pr_ref,
                issue_ref=args.issue_ref,
                url=args.url,
                provider_payload=_load_json_object(args.metadata_json)
                if args.metadata_json
                else None,
                fetch_metadata=args.fetch_metadata,
                fetch_timeout_seconds=args.fetch_timeout_seconds,
                maintainer_correction_input=(
                    _load_json_object(args.maintainer_correction_json)
                    if args.maintainer_correction_json
                    else None
                ),
                generated_at=generated_at,
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
            transition = payload.get("transition")
            if args.execute_transition:
                if registry_path is None:
                    raise ValueError("--execute-transition requires a LoopX registry")
                if not args.goal_id:
                    raise ValueError("--execute-transition requires --goal-id")
                if not args.claimed_by:
                    raise ValueError("--execute-transition requires --claimed-by")
                if not isinstance(transition, dict):
                    raise ValueError("PR lifecycle transition is missing")
                decision = str(transition.get("decision") or "")
                if decision in {"runnable_successor", "user_gate"}:
                    role = str(transition.get("role") or "agent")
                    todo_write = add_goal_todo(
                        registry_path=registry_path,
                        goal_id=args.goal_id,
                        role=role,
                        text=str(transition.get("text") or ""),
                        task_class=str(transition.get("task_class") or "advancement_task"),
                        action_kind=str(transition.get("action_kind") or ""),
                        required_write_scopes=(
                            list(transition.get("required_write_scopes") or [])
                            if role == "agent"
                            else None
                        ),
                        claimed_by=args.claimed_by if role == "agent" else None,
                        agent_id=args.claimed_by if role == "user" else None,
                        project=Path(args.project).expanduser(),
                    )
                    todo_changed = bool(
                        todo_write.get("added")
                        or todo_write.get("metadata_updated")
                        or todo_write.get("status_changed")
                    )
                    payload["todo_write"] = {
                        "schema_version": "issue_fix_maintainer_correction_todo_write_v0",
                        "write_performed": todo_changed,
                        "already_exists": bool(todo_write.get("already_exists")),
                        "todo_id": todo_write.get("todo_id"),
                        "role": todo_write.get("role"),
                        "claimed_by": todo_write.get("claimed_by"),
                        "blocks_agent": todo_write.get("blocks_agent"),
                        "path_recorded": False,
                    }
                    payload["todo_write_performed"] = todo_changed
                    writeback_contract = payload.get("writeback_contract")
                    if isinstance(writeback_contract, dict):
                        writeback_contract["todo_write_performed"] = bool(
                            todo_changed
                        )
                else:
                    payload["todo_write"] = {
                        "schema_version": "issue_fix_maintainer_correction_todo_write_v0",
                        "write_performed": False,
                        "already_exists": False,
                        "skip_reason": (
                            "unchanged_monitor_quiet"
                            if decision == "monitor_continuation"
                            else "terminal_or_no_followup"
                        ),
                        "path_recorded": False,
                    }
                validation = validate_issue_fix_pr_lifecycle_monitor_packet(payload)
                payload["validation"] = validation
                payload["ok"] = bool(validation["ok"])
            renderer = render_issue_fix_pr_lifecycle_monitor_markdown
        elif args.issue_fix_command == "outcome":
            if args.write_delivery_evidence and not args.delivery_evidence_json:
                raise ValueError(
                    "--write-delivery-evidence requires --delivery-evidence-json"
                )
            if args.write_delivery_evidence and args.feasibility_json:
                raise ValueError(
                    "--write-delivery-evidence uses the default feasibility domain-state row; "
                    "do not combine it with --feasibility-json"
                )
            provider_path = args.repository_memory_provider_json or (
                default_repository_memory_provider_config_path()
                if args.write_repository_memory
                else None
            )
            if args.write_repository_memory and not provider_path:
                raise ValueError(
                    "--write-repository-memory requires an explicit provider config "
                    "or LOOPX_ISSUE_FIX_REPOSITORY_MEMORY_PROVIDER_CONFIG"
                )
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
            explicit_delivery_evidence = (
                _load_json_object(args.delivery_evidence_json)
                if args.delivery_evidence_json
                else None
            )
            delivery_evidence = (
                compact_issue_fix_delivery_evidence(
                    explicit_delivery_evidence,
                )
                if explicit_delivery_evidence is not None
                else (
                    feasibility_packet.get("delivery_evidence")
                    if isinstance(feasibility_packet.get("delivery_evidence"), dict)
                    else None
                )
            )
            domain_state_write: dict[str, Any] | None = None
            if args.write_delivery_evidence:
                existing_delivery = feasibility_packet.get("delivery_evidence")
                existing_compact = (
                    compact_issue_fix_delivery_evidence(existing_delivery)
                    if isinstance(existing_delivery, dict)
                    else None
                )
                comparable_existing = (
                    {
                        key: value
                        for key, value in existing_compact.items()
                        if key != "recorded_at"
                    }
                    if existing_compact is not None
                    else None
                )
                comparable_delivery = (
                    {
                        key: value
                        for key, value in delivery_evidence.items()
                        if key != "recorded_at"
                    }
                    if delivery_evidence is not None
                    else None
                )
                if comparable_existing == comparable_delivery:
                    delivery_evidence = existing_delivery
                    write_result = {
                        "write_performed": False,
                        "status": "unchanged",
                        "row_count": None,
                    }
                else:
                    delivery_evidence = {
                        **delivery_evidence,
                        "recorded_at": generated_at,
                    }
                    feasibility_packet["delivery_evidence"] = delivery_evidence
                    write_result = upsert_issue_fix_feasibility_ledger_jsonl(
                        default_issue_fix_feasibility_ledger_path(
                            project=project,
                            goal_id=args.goal_id,
                        ),
                        feasibility_packet,
                    )
                domain_state_write = {
                    "schema_version": "issue_fix_delivery_evidence_writeback_v0",
                    "domain_pack": "issue_fix",
                    "stream": "feasibility",
                    "key": {"repo": args.repo, "issue_ref": args.issue_ref},
                    "write_performed": write_result.get("write_performed") is True,
                    "status": write_result.get("status"),
                    "row_count": write_result.get("row_count"),
                    "path_recorded": False,
                }
            payload = build_issue_fix_outcome_projection(
                goal_id=args.goal_id,
                feasibility_packet=feasibility_packet,
                pr_lifecycle_packet=pr_lifecycle_packet,
                delivery_evidence_input=delivery_evidence,
                agent_id=args.agent_id,
                generated_at=generated_at,
            )
            if args.write_repository_memory:
                if not args.repo_path:
                    raise ValueError(
                        "--write-repository-memory requires --repo-path for commit ancestry verification"
                    )
                outcome_case = (payload.get("issue_fix_outcomes") or [{}])[0]
                repository_context = (
                    outcome_case.get("repository_context")
                    if isinstance(outcome_case, dict)
                    else None
                )
                revision = (
                    str(repository_context.get("revision") or "").strip()
                    if isinstance(repository_context, dict)
                    else ""
                )
                if not revision:
                    raise ValueError(
                        "--write-repository-memory requires a revision-pinned outcome"
                    )
                writeback = write_issue_fix_validated_outcome_memory(
                    config=_load_json_object(str(provider_path)),
                    outcome_packet=payload,
                    repository_revision=revision,
                    repo_path=args.repo_path,
                    observed_at=generated_at,
                    execute=True,
                )
                payload["repository_memory_writeback"] = writeback
                payload["external_writes_performed"] = bool(
                    writeback.get("external_writes_performed")
                )
                payload["ok"] = writeback.get("ok") is True
                payload["source_contract"]["repository_memory_writeback"] = (
                    "issue_fix_validated_outcome_memory_writeback_v0"
                )
                payload["source_contract"]["writes_external_provider"] = bool(
                    writeback.get("external_writes_performed")
                )
                if payload["ok"] is not True:
                    payload["error"] = (
                        "repository memory writeback "
                        f"{writeback.get('status')}: "
                        f"{writeback.get('reason_code') or 'provider write failed'}"
                    )
            if domain_state_write is not None:
                payload["domain_state_write"] = domain_state_write
                payload["source_contract"]["writes_source_state"] = True
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
                generated_at=generated_at,
            )
            renderer = render_issue_fix_reviewer_recommendation_markdown
        elif args.issue_fix_command == "reviewer-request":
            if args.execute and args.metadata_json:
                raise ValueError(
                    "reviewer-request execute mode must fetch live PR metadata; "
                    "--metadata-json is preview-only"
                )
            notification_sinks_input = (
                _load_json_object(args.notification_sinks_json)
                if args.notification_sinks_json
                else None
            )
            notification_sinks_source = (
                "explicit" if notification_sinks_input is not None else "not_configured"
            )
            notification_lifecycle_packet: dict[str, Any] | None = None
            notification_lifecycle_path: Path | None = None
            notification_lifecycle_materialized = False
            if args.goal_id:
                goal, requested_project = _load_goal_for_project(
                    registry_path=registry_path,
                    goal_id=args.goal_id,
                    project=args.project,
                )
                if notification_sinks_input is None:
                    notification_sinks_input = (
                        load_goal_reviewer_notification_sinks_input(
                            goal=goal,
                            project=requested_project,
                        )
                    )
                if notification_sinks_input is not None:
                    if notification_sinks_source == "not_configured":
                        notification_sinks_source = "goal_default"
                    reference = normalise_github_issue_reference(
                        repo="public_repo_fixture",
                        issue_ref="pull_request_fixture",
                        url=args.url,
                    )
                    if reference.get("kind") != "pull_request":
                        raise ValueError(
                            "goal-scoped reviewer notification requires a GitHub PR"
                        )
                    notification_lifecycle_path = (
                        default_issue_fix_domain_state_ledger_path(
                            project=requested_project,
                            goal_id=args.goal_id,
                        )
                    )
                    try:
                        notification_lifecycle_packet = _load_jsonl_row(
                            notification_lifecycle_path,
                            repo=str(reference["repo"]),
                            ref_field="pr_ref",
                            ref_value=f"pull_{int(reference['number'])}",
                        )
                    except ValueError:
                        if args.execute:
                            try:
                                notification_lifecycle_packet = (
                                    _materialize_goal_reviewer_notification_lifecycle(
                                        ledger_path=notification_lifecycle_path,
                                        url=args.url,
                                        generated_at=generated_at,
                                        fetch_metadata=True,
                                    )
                                )
                            except (OSError, RuntimeError, ValueError):
                                raise ValueError(
                                    "goal-scoped reviewer notification could not "
                                    "materialize a verified PR lifecycle row before "
                                    "external send"
                                ) from None
                            notification_lifecycle_materialized = True
                    notification_sinks_input = with_reviewer_notification_receipts(
                        notification_sinks_input,
                        reviewer_notification_receipts_from_state(
                            notification_lifecycle_packet
                        ),
                    )
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
                notification_sinks_input=notification_sinks_input,
                provider_payload=(
                    _load_json_object(args.metadata_json)
                    if args.metadata_json
                    else None
                ),
                execute=args.execute,
                generated_at=generated_at,
            )
            payload["secondary_notification_source"] = notification_sinks_source
            payload["secondary_notification_lifecycle_materialized"] = (
                notification_lifecycle_materialized
            )
            payload["secondary_notification_receipts_persisted"] = False
            secondary = payload.get("secondary_notifications")
            new_receipts = (
                secondary.get("receipts")
                if isinstance(secondary, dict)
                and isinstance(secondary.get("receipts"), list)
                else []
            )
            if (
                args.execute
                and notification_lifecycle_packet is not None
                and notification_lifecycle_path is not None
                and new_receipts
            ):
                try:
                    write_result = persist_issue_fix_reviewer_notification_receipts(
                        notification_lifecycle_path,
                        notification_lifecycle_packet,
                        list(new_receipts),
                    )
                except (OSError, ValueError):
                    payload["ok"] = False
                    payload["secondary_notification_receipt_blocker"] = (
                        "reviewer_notification_receipt_persistence_failed"
                    )
                else:
                    payload["secondary_notification_receipt_write"] = {
                        "schema_version": (
                            "issue_fix_reviewer_notification_receipt_write_v0"
                        ),
                        "domain_pack": "issue_fix",
                        "stream": "pr_lifecycle",
                        "write_performed": (
                            write_result.get("write_performed") is True
                        ),
                        "status": write_result.get("status"),
                        "path_recorded": False,
                    }
                    payload["secondary_notification_receipts_persisted"] = True
            renderer = render_issue_fix_reviewer_request_markdown
        elif args.issue_fix_command == "acceptance-fixture":
            payload = build_issue_fix_acceptance_fixture_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                generated_at=generated_at,
            )
            renderer = render_issue_fix_acceptance_loop_markdown
        elif args.issue_fix_command == "repo-branch-fixture":
            payload = build_issue_fix_repo_branch_fixture_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                generated_at=generated_at,
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
                generated_at=generated_at,
            )
            renderer = render_issue_fix_acceptance_loop_markdown
        else:
            raise ValueError(
                "issue-fix requires `repository-memory-sync`, `workflow-plan`, `feasibility`, "
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
            render_issue_fix_repository_memory_sync_markdown
            if getattr(args, "issue_fix_command", None) == "repository-memory-sync"
            else render_issue_fix_workflow_plan_markdown
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
