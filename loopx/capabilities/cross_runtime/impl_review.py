from __future__ import annotations

import re
from typing import Any


CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION = "cross_runtime_impl_review_demo_packet_v0"
DEFAULT_REQUIREMENT = "Implement a bounded user-visible change and produce verifier evidence."
DEFAULT_VERIFIER = "project-specific smoke or test command"
DEFAULT_GOAL_ID = "cross-runtime-impl-review-demo"
DEFAULT_IMPLEMENTER_AGENT_ID = "claude-code-impl"
DEFAULT_REVIEWER_AGENT_ID = "codex-review"

PRIVATE_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:OPENAI|ANTHROPIC|AWS|GITHUB)_[A-Z0-9_]*KEY\b"),
)


def _compact(value: str) -> str:
    return " ".join(str(value or "").split())


def _public_safe_text(value: str, *, field: str) -> tuple[bool, str | None]:
    text = _compact(value)
    if not text:
        return False, f"{field} must not be empty"
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            return False, f"{field} contains private-looking material"
    return True, None


def _todo_text(prefix: str, body: str) -> str:
    return f"[P0] {prefix}: {body}"


def build_cross_runtime_impl_review_demo_packet(
    *,
    preset: str = "claude-codex",
    dry_run: bool = True,
    goal_id: str = DEFAULT_GOAL_ID,
    requirement: str = DEFAULT_REQUIREMENT,
    implementer_agent_id: str = DEFAULT_IMPLEMENTER_AGENT_ID,
    reviewer_agent_id: str = DEFAULT_REVIEWER_AGENT_ID,
    verifier: str = DEFAULT_VERIFIER,
    generated_at: str = "2026-06-30T00:00:00Z",
) -> dict[str, Any]:
    """Build a public-safe dry-run packet for a Claude Code + Codex review demo."""

    if preset != "claude-codex":
        return {
            "ok": False,
            "schema_version": CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION,
            "preset": preset,
            "dry_run": dry_run,
            "error": "unsupported preset; supported presets: claude-codex",
        }
    if not dry_run:
        return {
            "ok": False,
            "schema_version": CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION,
            "preset": preset,
            "dry_run": False,
            "error": "impl-review demo is dry-run only; pass --dry-run",
        }

    for field, value in {
        "goal_id": goal_id,
        "requirement": requirement,
        "implementer_agent_id": implementer_agent_id,
        "reviewer_agent_id": reviewer_agent_id,
        "verifier": verifier,
    }.items():
        ok, error = _public_safe_text(value, field=field)
        if not ok:
            return {
                "ok": False,
                "schema_version": CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION,
                "preset": preset,
                "dry_run": dry_run,
                "error": error,
            }

    requirement = _compact(requirement)
    verifier = _compact(verifier)
    implementation_todo = _todo_text(
        "Implement bounded requirement",
        requirement,
    )
    review_todo = _todo_text(
        "Review implementation evidence",
        "produce PASS/BLOCK/INCONCLUSIVE verdict with verifier and handoff.",
    )

    planned_todos = [
        {
            "todo_key": "implementation",
            "role": "agent",
            "priority": "P0",
            "claimed_by": implementer_agent_id,
            "runtime": "claude_code",
            "action_kind": "cross_runtime_implementation",
            "text": implementation_todo,
            "would_write": False,
            "owned_outputs": [
                "patch summary",
                "changed files summary",
                "first verifier attempt",
                "implementation evidence summary",
            ],
            "must_not": [
                "approve its own review gate",
                "publish, merge, or comment externally without owner approval",
                "include raw Claude Code transcript",
            ],
        },
        {
            "todo_key": "review",
            "role": "agent",
            "priority": "P0",
            "claimed_by": reviewer_agent_id,
            "runtime": "codex",
            "action_kind": "cross_runtime_review",
            "text": review_todo,
            "would_write": False,
            "owned_outputs": [
                "review verdict",
                "blocker list",
                "verifier recommendation",
                "next handoff",
            ],
            "must_not": [
                "rewrite the implementation without a fix todo",
                "treat style preferences as blockers",
                "include raw Codex transcript",
            ],
        },
    ]

    commands = [
        {
            "step": "add_implementation_todo",
            "command": (
                f"loopx todo add --goal-id {goal_id} --role agent "
                f"--text {implementation_todo!r} --claimed-by {implementer_agent_id}"
            ),
            "would_write": True,
            "execution_allowed_in_packet": False,
        },
        {
            "step": "add_review_todo",
            "command": (
                f"loopx todo add --goal-id {goal_id} --role agent "
                f"--text {review_todo!r} --claimed-by {reviewer_agent_id}"
            ),
            "would_write": True,
            "execution_allowed_in_packet": False,
        },
        {
            "step": "check_implementation_quota",
            "command": (
                f"loopx --format json quota should-run --goal-id {goal_id} "
                f"--agent-id {implementer_agent_id} --runtime-profile generic_cli"
            ),
            "would_write": False,
            "execution_allowed_in_packet": False,
        },
        {
            "step": "claim_implementation_todo",
            "command": (
                f"loopx todo claim --goal-id {goal_id} --todo-id <implementation_todo_id> "
                f"--claimed-by {implementer_agent_id}"
            ),
            "would_write": True,
            "execution_allowed_in_packet": False,
        },
        {
            "step": "handoff_review_packet",
            "command": f"loopx review-packet --goal-id {goal_id}",
            "would_write": False,
            "execution_allowed_in_packet": False,
        },
        {
            "step": "check_review_quota",
            "command": (
                f"loopx --format json quota should-run --goal-id {goal_id} "
                f"--agent-id {reviewer_agent_id} --runtime-profile generic_cli"
            ),
            "would_write": False,
            "execution_allowed_in_packet": False,
        },
    ]

    review_verdict_contract = {
        "verdict": "PASS | BLOCK | INCONCLUSIVE",
        "blockers": (
            "objective defects only: failing tests, broken behavior, unmet "
            "requirement, unsafe boundary"
        ),
        "suggestions": "non-blocking style, naming, or follow-up notes",
        "verifier": verifier,
        "handoff": "implementer fix | reviewer accept | user gate | archive",
    }

    return {
        "ok": True,
        "schema_version": CROSS_RUNTIME_IMPL_REVIEW_DEMO_SCHEMA_VERSION,
        "preset": preset,
        "generated_at": generated_at,
        "dry_run": True,
        "writes_state": False,
        "launches_runtime": False,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "raw_transcripts_captured": False,
        "goal_id": goal_id,
        "requirement": requirement,
        "verifier": verifier,
        "roles": {
            "implementer": {
                "agent_id": implementer_agent_id,
                "runtime": "claude_code",
                "visible_entry": ["/loopx <implementation goal>", "/loop"],
            },
            "reviewer": {
                "agent_id": reviewer_agent_id,
                "runtime": "codex",
                "visible_entry": ["/loopx Review <implementation evidence>"],
            },
        },
        "planned_todos": planned_todos,
        "commands": commands,
        "review_verdict_contract": review_verdict_contract,
        "evidence_boundary": {
            "allowed": [
                "public-safe requirement summary",
                "todo ids and agent ids",
                "changed-file summary",
                "verifier command and pass/fail/inconclusive label",
                "review verdict and blocker titles",
                "review-packet or dashboard links",
            ],
            "forbidden": [
                "raw Claude or Codex transcripts",
                "private prompts, credentials, local secrets, or private document links",
                "raw benchmark task text, trajectories, logs, or verifier tails",
                "unpublished maintainer messages",
                "permission changes, merge, publish, or external comments without owner gate",
            ],
        },
        "stop_conditions": [
            "user gate required",
            "source or write boundary unclear",
            "verifier missing or inconclusive",
            "reviewer BLOCK verdict with no bounded fix todo",
        ],
    }


def render_cross_runtime_impl_review_demo_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cross-Runtime Impl/Review Demo Packet",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- schema_version: `{payload.get('schema_version')}`",
        f"- preset: `{payload.get('preset')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- writes_state: `{payload.get('writes_state')}`",
        f"- launches_runtime: `{payload.get('launches_runtime')}`",
    ]
    if not payload.get("ok"):
        lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- verifier: `{payload.get('verifier')}`",
            "",
            "## Planned Todos",
        ]
    )
    for todo in payload.get("planned_todos", []):
        if isinstance(todo, dict):
            lines.append(
                f"- `{todo.get('todo_key')}` `{todo.get('claimed_by')}` "
                f"{todo.get('text')}"
            )
    lines.extend(["", "## Commands"])
    for command in payload.get("commands", []):
        if isinstance(command, dict):
            lines.append(f"- `{command.get('command')}`")
    lines.extend(["", "## Review Verdict"])
    verdict = payload.get("review_verdict_contract")
    if isinstance(verdict, dict):
        for key, value in verdict.items():
            lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Boundary"])
    boundary = payload.get("evidence_boundary")
    if isinstance(boundary, dict):
        allowed = "; ".join(str(item) for item in boundary.get("allowed", []))
        forbidden = "; ".join(str(item) for item in boundary.get("forbidden", []))
        lines.append(f"- allowed: {allowed}")
        lines.append(f"- forbidden: {forbidden}")
    return "\n".join(lines).rstrip() + "\n"
