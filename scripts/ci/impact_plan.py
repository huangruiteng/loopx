"""Exact-path, fail-closed CI impact planning; candidate plans are shadow-only."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import subprocess


SCHEMA = "loopx_ci_impact_plan_v1"
ROOT_DOCS = {"README.md", "README.zh-CN.md", "CHANGELOG.md", "CONTRIBUTING.md"}

# This is a reviewed behavioral boundary, not a filename/keyword search. The
# checkpoint has callers across refresh, quota, settlement and terminal routing.
VISION_SOURCES = (
    "loopx/control_plane/goals/vision_checkpoint.ts",
    "loopx/control_plane/goals/goal_vision.py",
)
VISION_TESTS = (
    "tests/control_plane/test_vision_checkpoint_runtime.py",
    "tests/control_plane/test_vision_budget_cli.py",
    "tests/control_plane/test_goal_vision_succession.py",
    "tests/control_plane/test_goal_vision_blocked_successor.py",
    "tests/control_plane/test_vision_wait_coverage.py",
    "tests/control_plane/test_refresh_checkpoint_recovery.py",
    "tests/control_plane/test_refresh_checkpoint_isolation.py",
    "tests/control_plane/test_refresh_state_replan_gate.py",
    "tests/control_plane/test_goal_frontier_replan_rules.py",
    "tests/control_plane/test_goal_terminal_no_followup.py",
    "tests/control_plane/test_autonomous_replan_ack.py",
    "tests/control_plane/test_monitor_replan_agent_scope.py",
    "tests/control_plane/test_monitor_followthrough_contract.py",
    "tests/control_plane/test_quota_settlement_cli.py",
    "tests/control_plane/test_quota_cli_projection.py",
    "tests/control_plane/test_public_safe_text_owner_parity.py",
    "tests/control_plane/test_run_context_retention.py",
    "tests/cli_commands/test_quota_turn_envelope_validation_failure.py",
)
VISION_SMOKES = (
    "examples/project/goal-vision-refresh-state-budget-smoke.py",
    "examples/project/goal-vision-path-delta-smoke.py",
    "examples/project/goal-vision-replan-contract-smoke.py",
    "examples/project/goal-vision-closed-successor-smoke.py",
    "examples/control_plane/status-quota-perf-budget-smoke.py",
)
VISION_TS_TESTS = (
    "tests/control_plane_ts/vision_checkpoint.test.ts",
    "tests/control_plane_ts/vision_wait_coverage.test.ts",
    "tests/control_plane_ts/refresh_recovery.test.ts",
    "tests/control_plane_ts/replan_settlement.test.ts",
    "tests/control_plane_ts/turn_settlement.test.ts",
)
VISION_PATHS = frozenset((*VISION_SOURCES, *VISION_TESTS, *VISION_SMOKES, *VISION_TS_TESTS))


@dataclass(frozen=True)
class Change:
    status: str
    path: str


def is_document(path: str) -> bool:
    return path in ROOT_DOCS or (path.startswith("docs/") and PurePosixPath(path).suffix == ".md")


def candidate(changes: list[Change], *, pull_request: bool = True) -> tuple[str, str]:
    if not pull_request:
        return "full", "non-PR events always qualify the full suite"
    if not changes:
        return "full", "empty or unavailable impact is not an exemption"
    for change in changes:
        path = PurePosixPath(change.path)
        if path.is_absolute() or ".." in path.parts or str(path) != change.path:
            return "full", "non-canonical path requires full qualification"
        if change.status not in {"A", "M", "D"}:
            return "full", "type changes or unrecognized Git statuses require full qualification"
    code = [change for change in changes if not is_document(change.path)]
    if not code:
        return "docs", "only existing documentation exemptions changed"
    if any(change.path not in VISION_PATHS for change in code):
        return "full", "unmapped or shared-boundary change requires full qualification"
    if any(change.status == "D" or (change.status == "A" and change.path in VISION_SOURCES) for change in code):
        return "full", "runtime additions, deletions and renames require full qualification"
    return "vision", "checkpoint authoring and its read/refresh/replan/settlement consumers"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def revision(ref: str) -> str:
    return git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()


def diff_changes(base: str, head: str) -> list[Change]:
    raw = git("diff", "--name-status", "--no-renames", "-z", base, head, "--").split(b"\0")
    if raw[-1] != b"" or (len(raw) - 1) % 2:
        raise ValueError("malformed NUL-delimited Git change list")
    return [Change(os.fsdecode(raw[i]), os.fsdecode(raw[i + 1])) for i in range(0, len(raw) - 1, 2)]


def plan(base: str, head: str, *, pull_request: bool = True) -> dict:
    base_sha, head_sha = revision(base), revision(head)
    merge_base = git("merge-base", base_sha, head_sha).decode().strip()
    changes = diff_changes(merge_base, head_sha)
    profile, reason = candidate(changes, pull_request=pull_request)
    # CI-policy edits rehearse the candidate too, but can never select less than
    # full qualification. This also exercises the new job before rollout.
    policy_changed = any(item.path.startswith("scripts/ci/") or item.path == ".github/workflows/python-tests.yml" for item in changes)
    shadow = "vision" if pull_request and (profile == "vision" or policy_changed) else "none"
    return {
        "schema_version": SCHEMA,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_base_sha": merge_base,
        "checkout_sha": revision("HEAD"),
        "candidate_profile": profile,
        "shadow_profile": shadow,
        "execution_mode": "docs" if profile == "docs" else "full_with_shadow" if shadow == "vision" else "full",
        "reason": reason,
        "changes": [{"status": item.status, "path": item.path} for item in changes],
        "pytest_files": list(VISION_TESTS) if shadow == "vision" else [],
        "smoke_files": list(VISION_SMOKES) if shadow == "vision" else [],
        "shared_checks": [] if profile == "docs" else ["full TS tests and typecheck", "lint", "CLI output budgets"],
        "coverage_scope": "full suite remains authoritative; shadow is selected-only",
        "selection_is_merge_authority": False,
    }


def write_plan(packet: dict, output: str) -> None:
    Path(output).write_text(json.dumps(packet, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def validate_shadow_plan(packet: dict) -> None:
    if packet.get("schema_version") != SCHEMA or packet.get("candidate_profile") not in {"vision", "full"} or packet.get("shadow_profile") != "vision":
        raise ValueError("not a supported vision shadow plan")
    if packet.get("execution_mode") != "full_with_shadow" or packet.get("selection_is_merge_authority") is not False:
        raise ValueError("this rollout cannot authorize selective-only qualification")
    if packet.get("pytest_files") != list(VISION_TESTS) or packet.get("smoke_files") != list(VISION_SMOKES):
        raise ValueError("plan does not contain the complete reviewed test inventory")
    if packet.get("checkout_sha") != revision("HEAD"):
        raise ValueError("plan belongs to a different tested checkout")
    for ref in ("base_sha", "head_sha", "merge_base_sha"):
        sha = packet.get(ref, "")
        if not isinstance(sha, str) or len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
            raise ValueError("plan contains an invalid immutable revision")
    if plan(packet["base_sha"], packet["head_sha"]) != packet:
        raise ValueError("plan cannot be reproduced from its exact Git revisions")
    for path in (*VISION_TESTS, *VISION_SMOKES):
        if not Path(path).is_file() or Path(path).is_symlink():
            raise ValueError(f"selected check is missing or not a regular file: {path}")
