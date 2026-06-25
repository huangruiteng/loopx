from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CAPABILITY_CATALOG_SCHEMA_VERSION = "loopx_capability_catalog_v0"
CAPABILITY_DETAIL_SCHEMA_VERSION = "loopx_capability_detail_v0"


CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "id": "issue-fix",
        "title": "Repo issue-fix loop",
        "status": "active-preview",
        "real_world_anchor": "open-source issue/PR solver",
        "user_value": (
            "Turn a public GitHub issue or PR signal into a caller-approved "
            "local issue branch with validation evidence and a PR-review packet."
        ),
        "entry_command": "loopx issue-fix caller-repo-branch --repo-path <repo> --execute --format json",
        "commands": [
            {
                "command": "loopx content-ops issue-fix-metadata-preview --url <github-issue-url> --fetch-metadata --format json",
                "purpose": "Fetch body-free public GitHub issue/PR metadata.",
                "write_boundary": "read-only external metadata; no issue comment, PR, or todo write",
            },
            {
                "command": "loopx content-ops issue-fix-intake --format json",
                "purpose": "Project public issue metadata into an issue-fix intake packet.",
                "write_boundary": "fixture-only; no external read or write",
            },
            {
                "command": "loopx issue-fix acceptance-fixture --format json",
                "purpose": "Prove the failure-before/fix-after acceptance loop on a deterministic fixture.",
                "write_boundary": "temporary local fixture only",
            },
            {
                "command": "loopx issue-fix repo-branch-fixture --format json",
                "purpose": "Exercise the same loop through a temporary git issue branch.",
                "write_boundary": "temporary local git fixture only",
            },
            {
                "command": "loopx issue-fix caller-repo-branch --repo-path <repo> --validation-command <cmd> --execute --format json",
                "purpose": "Create or claim a caller-approved local issue branch and run caller-declared validation.",
                "write_boundary": "approved local repo only; no external comment, PR creation, merge, or publish",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "github_issue_metadata_preview_v0",
                "module": "loopx.capabilities.issue_fix.metadata_preview",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_issue_fix_metadata_preview_packet_v0",
                "module": "loopx.capabilities.issue_fix.intake_surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_issue_fix_intake_packet_v0",
                "module": "loopx.capabilities.issue_fix.intake_surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "issue_fix_intake_v0",
                "module": "loopx.capabilities.issue_fix.intake_surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "issue_fix_acceptance_loop_v0",
                "module": "loopx.capabilities.issue_fix.acceptance_loop",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-acceptance-loop-v0.md",
            },
            {
                "schema_version": "issue_fix_validated_fix_artifact_v0",
                "module": "loopx.capabilities.issue_fix.acceptance_loop",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-acceptance-loop-v0.md",
            },
            {
                "schema_version": "issue_fix_caller_repo_branch_packet_v0",
                "module": "loopx.capabilities.issue_fix.acceptance_loop",
                "doc": "docs/capabilities/issue-fix/protocols/issue-fix-acceptance-loop-v0.md",
            },
        ],
        "smokes": [
            "python3 examples/content-ops-issue-fix-metadata-preview-smoke.py",
            "python3 examples/content-ops-issue-fix-intake-smoke.py",
            "python3 examples/issue-fix-acceptance-loop-smoke.py",
        ],
        "docs": [
            "docs/capabilities/issue-fix/README.md",
            "docs/capabilities/issue-fix/protocols/issue-fix-acceptance-loop-v0.md",
            "docs/reference/protocols/content-ops-surface-v0.md",
            "docs/reference/protocols/issue-fix-acceptance-loop-v0.md",
        ],
        "boundaries": [
            "GitHub issue body, comments, timeline, and raw provider payloads are gated and not copied.",
            "Caller repo mode reads and writes only the explicitly approved local git repo.",
            "External comments, PR creation, merge, publish, and destructive git remain out of scope.",
        ],
        "next_real_step": (
            "Put an agent patching step between branch preparation and PR-ready "
            "packet generation, while keeping external PR/comment actions explicit."
        ),
    },
    {
        "id": "content-ops",
        "title": "Creator/content operations loop",
        "status": "active-preview",
        "real_world_anchor": "self-media operations and public/private source intake",
        "user_value": (
            "Collect public handles and approved private-connector metadata into "
            "reviewable source, angle, draft, feedback, and publish-gate packets."
        ),
        "entry_command": "loopx content-ops aggregate-packets --format json",
        "commands": [
            {
                "command": "loopx content-ops exploration-plan --format json",
                "purpose": "Plan source lanes before reading connector material.",
                "write_boundary": "fixture-only; no source read",
            },
            {
                "command": "loopx content-ops observe-public-handle --url <public-url> --source-item-id <id> --format json",
                "purpose": "Create a metadata-only public source item.",
                "write_boundary": "public HEAD-only metadata read unless --no-fetch is used",
            },
            {
                "command": "loopx content-ops project-private-connector-gate --format json",
                "purpose": "Represent a private connector as an owner gate before metadata intake.",
                "write_boundary": "no private connector read",
            },
            {
                "command": "loopx content-ops project-chatview-report --format json",
                "purpose": "Summarize approved ChatView connector counts without raw chat content.",
                "write_boundary": "compact counts only; no raw message text",
            },
            {
                "command": "loopx content-ops aggregate-packets --format json",
                "purpose": "Merge public source packets and private owner gates into a control-plane surface.",
                "write_boundary": "local packet aggregation only",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "content_ops_surface_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "source_item_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_private_connector_owner_gate_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_packet_aggregation_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
            {
                "schema_version": "content_ops_chatview_connector_report_v0",
                "module": "loopx.capabilities.content_ops.surface",
                "doc": "docs/reference/protocols/content-ops-surface-v0.md",
            },
        ],
        "smokes": [
            "python3 examples/content-ops-exploration-plan-smoke.py",
            "python3 examples/content-ops-public-handle-observation-smoke.py",
            "python3 examples/content-ops-private-connector-gate-smoke.py",
            "python3 examples/content-ops-chatview-report-smoke.py",
            "python3 examples/content-ops-packet-aggregation-smoke.py",
        ],
        "docs": [
            "docs/capabilities/content-ops/README.md",
            "docs/reference/protocols/content-ops-surface-v0.md",
        ],
        "boundaries": [
            "Private connectors enter as owner gates or compact approved counts first.",
            "Raw chats, transcripts, auth material, logs, and local paths are not copied into public packets.",
            "Publish remains blocked until an explicit user decision.",
        ],
        "next_real_step": (
            "Turn the aggregated surface into a small review/feed UI where a user "
            "can score source items, angles, and drafts."
        ),
    },
    {
        "id": "value-connectors",
        "title": "External value connector starters",
        "status": "active-preview",
        "real_world_anchor": "external channel intake for revenue, cost, demand, and connector reuse",
        "user_value": (
            "Install and run public-safe connector starters that turn external "
            "channel metadata into LoopX value signals while gating account "
            "setup, sends, posts, and private reads."
        ),
        "entry_command": "loopx value-connectors install-check --format json",
        "commands": [
            {
                "command": "loopx value-connectors install-check --format json",
                "purpose": "Show connector starter install/use commands and local dependency status.",
                "write_boundary": "local check only; no external read or write",
            },
            {
                "command": "loopx value-connectors github-public-probe --url <github-issue-or-pr-url> --format json",
                "purpose": "Validate a public GitHub channel URL and build a connector call packet.",
                "write_boundary": "no network read unless --fetch-metadata is provided",
            },
            {
                "command": "loopx value-connectors github-public-probe --url <github-issue-or-pr-url> --fetch-metadata --format json",
                "purpose": "Fetch allowlisted public GitHub metadata without body/comment/timeline content.",
                "write_boundary": "public metadata read only; no comments, PRs, account changes, or writes",
            },
            {
                "command": "loopx value-connectors github-reply-monitor --issue-url <github-issue-or-pr-url> --after-comment-url <github-issue-comment-url> --fetch-metadata --format json",
                "purpose": "Detect public maintainer replies after a LoopX comment without capturing comment bodies.",
                "write_boundary": "public comment metadata read only; no comment bodies, thread bump, or external write",
            },
            {
                "command": "loopx value-connectors plan --connector-id <id> ... --format json",
                "purpose": "Plan gated account setup, external replies, sends, or future connector calls.",
                "write_boundary": "plan-only; external writes and account setup require exact approval",
            },
        ],
        "implemented_protocols": [
            {
                "schema_version": "value_connector_plan_v0",
                "module": "loopx.capabilities.value_connectors.planner",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "connector_call_intent_v0",
                "module": "loopx.capabilities.value_connectors.planner",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "connector_approval_gate_v0",
                "module": "loopx.capabilities.value_connectors.planner",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "github_public_channel_probe_packet_v0",
                "module": "loopx.capabilities.value_connectors.github_public",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "github_public_reply_monitor_packet_v0",
                "module": "loopx.capabilities.value_connectors.github_public",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
            {
                "schema_version": "value_connector_install_check_packet_v0",
                "module": "loopx.capabilities.value_connectors.github_public",
                "doc": "docs/reference/protocols/value-connector-plan-v0.md",
            },
        ],
        "smokes": [
            "python3 examples/value-connectors-github-public-probe-smoke.py",
        ],
        "docs": [
            "docs/capabilities/value-connectors/README.md",
            "docs/reference/protocols/value-connector-plan-v0.md",
        ],
        "boundaries": [
            "The GitHub starter copies allowlisted public metadata only, not bodies, comments, timelines, raw provider payloads, auth material, or local paths.",
            "The reply monitor reads or accepts comment metadata only: author, association, timestamps, and URL; it never bumps a thread.",
            "Account signup, email sends, community posts, public replies, private reads, paid services, and production actions remain gated exact-call actions.",
            "Every connector call must include a money, cost, demand, or capability metric plus a kill condition.",
        ],
        "next_real_step": (
            "Use reply-monitor signals to graduate only explicit maintainer interest "
            "into public triage notes or paid-path discovery; otherwise stop without bumps."
        ),
    },
)


def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "title": record["title"],
        "status": record["status"],
        "real_world_anchor": record["real_world_anchor"],
        "entry_command": record["entry_command"],
        "implemented_protocol_count": len(record.get("implemented_protocols") or []),
        "smoke_count": len(record.get("smokes") or []),
        "next_real_step": record["next_real_step"],
    }


def capability_ids() -> list[str]:
    return [str(record["id"]) for record in CAPABILITIES]


def get_capability(capability_id: str) -> dict[str, Any]:
    wanted = str(capability_id or "").strip()
    for record in CAPABILITIES:
        if record["id"] == wanted:
            return dict(record)
    raise ValueError(f"unknown capability `{wanted}`; expected one of {capability_ids()}")


def build_capability_catalog_packet() -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": CAPABILITY_CATALOG_SCHEMA_VERSION,
        "capabilities": [_summary(record) for record in CAPABILITIES],
    }


def build_capability_detail_packet(capability_id: str) -> dict[str, Any]:
    record = get_capability(capability_id)
    return {
        "ok": True,
        "schema_version": CAPABILITY_DETAIL_SCHEMA_VERSION,
        "capability": record,
    }


def render_capability_catalog_markdown(payload: dict[str, Any]) -> str:
    lines = ["# LoopX Capabilities", ""]
    for item in payload.get("capabilities") or []:
        if not isinstance(item, Mapping):
            continue
        lines.extend(
            [
                f"## {item.get('id')}: {item.get('title')}",
                "",
                f"- status: `{item.get('status')}`",
                f"- anchor: {item.get('real_world_anchor')}",
                f"- entry: `{item.get('entry_command')}`",
                f"- implemented_protocol_count: `{item.get('implemented_protocol_count')}`",
                f"- smoke_count: `{item.get('smoke_count')}`",
                f"- next: {item.get('next_real_step')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_capability_detail_markdown(payload: dict[str, Any]) -> str:
    record = payload.get("capability")
    if not isinstance(record, Mapping):
        return "# LoopX Capability\n\nNo capability found.\n"
    lines = [
        f"# LoopX Capability: {record.get('title')}",
        "",
        f"- id: `{record.get('id')}`",
        f"- status: `{record.get('status')}`",
        f"- anchor: {record.get('real_world_anchor')}",
        f"- value: {record.get('user_value')}",
        f"- entry: `{record.get('entry_command')}`",
        "",
        "## Commands",
        "",
    ]
    for item in record.get("commands") or []:
        if not isinstance(item, Mapping):
            continue
        lines.extend(
            [
                f"- `{item.get('command')}`",
                f"  - purpose: {item.get('purpose')}",
                f"  - boundary: {item.get('write_boundary')}",
            ]
        )
    lines.extend(["", "## Implemented Protocols", ""])
    for item in record.get("implemented_protocols") or []:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            f"- `{item.get('schema_version')}` in `{item.get('module')}` "
            f"([{item.get('doc')}]({item.get('doc')}))"
        )
    lines.extend(["", "## Smokes", ""])
    for smoke in record.get("smokes") or []:
        lines.append(f"- `{smoke}`")
    lines.extend(["", "## Boundaries", ""])
    for boundary in record.get("boundaries") or []:
        lines.append(f"- {boundary}")
    lines.extend(["", "## Next Real Step", "", str(record.get("next_real_step"))])
    return "\n".join(lines).rstrip() + "\n"
