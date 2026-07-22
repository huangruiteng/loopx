from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..content_ops.social_browser_x import (
    SOCIAL_BROWSER_X_PROVIDER_MODULE,
    build_social_browser_x_provider_packet,
)
from .finance_extension_migration import (
    build_finance_extension_migration_contract,
)


VALUE_CONNECTOR_SOURCE_MAP_PACKET_SCHEMA_VERSION = (
    "value_connector_source_map_packet_v0"
)
VALUE_CONNECTOR_SOURCE_PROFILE_SCHEMA_VERSION = "value_connector_source_profile_v0"
VALUE_CONNECTOR_SOURCE_MAP_PROJECTION_SCHEMA_VERSION = (
    "value_connector_source_map_projection_v0"
)


SOURCE_PROFILE_IDS = {
    "all",
    "github_public_channel",
    "github_public_reply_monitor",
    "content_ops_public_handle",
    "social_browser_x",
    "agent_reach_ops_source_map",
    "finance_market_snapshot",
}

OUTCOME_PROVIDER_BINDINGS: dict[str, dict[str, str | None]] = {
    "github_public_channel": {
        "outcome_capability_id": "issue-fix",
        "provider_binding_state": "migrated",
        "provider_module": "loopx.capabilities.issue_fix.github_public",
    },
    "github_public_reply_monitor": {
        "outcome_capability_id": "issue-fix",
        "provider_binding_state": "migrated",
        "provider_module": "loopx.capabilities.issue_fix.github_public",
    },
    "content_ops_public_handle": {
        "outcome_capability_id": "content-ops",
        "provider_binding_state": "native",
        "provider_module": "loopx.capabilities.content_ops.surface",
    },
    "social_browser_x": {
        "outcome_capability_id": "content-ops",
        "provider_binding_state": "migrated",
        "provider_module": SOCIAL_BROWSER_X_PROVIDER_MODULE,
    },
    "agent_reach_ops_source_map": {
        "outcome_capability_id": "content-ops",
        "provider_binding_state": "mapped",
        "provider_module": None,
    },
    "finance_market_snapshot": {
        "outcome_capability_id": None,
        "provider_binding_state": "migrated_to_extension",
        "provider_module": None,
    },
    "botmail_identity": {
        "outcome_capability_id": "content-ops",
        "provider_binding_state": "mapped",
        "provider_module": None,
    },
    "community_channel": {
        "outcome_capability_id": "content-ops",
        "provider_binding_state": "mapped",
        "provider_module": None,
    },
}


def _outcome_provider_binding(connector_id: str) -> dict[str, str | None]:
    binding = OUTCOME_PROVIDER_BINDINGS.get(connector_id)
    if binding is None:
        raise ValueError(f"connector {connector_id!r} has no outcome provider binding")
    return dict(binding)


def _source_profile(
    *,
    connector_id: str,
    status: str,
    route_type: str,
    boundary: str,
    safe_uses: list[str],
    commands: list[str],
    evidence_schema: str,
    maturity_hint: str,
    write_gate: str | None = None,
    stop_conditions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": VALUE_CONNECTOR_SOURCE_PROFILE_SCHEMA_VERSION,
        "connector_id": connector_id,
        "status": status,
        "route_type": route_type,
        "boundary": boundary,
        "safe_uses": safe_uses,
        "commands": commands,
        "evidence_schema": evidence_schema,
        "maturity_hint": maturity_hint,
        "external_reads_allowed": boundary
        in {
            "public_metadata_only",
            "public_no_login",
            "logged_in_read",
            "route_specific_read_only",
        },
        "external_writes_allowed": False,
        "write_gate": write_gate,
        "stop_conditions": stop_conditions
        or [
            "source boundary is unclear",
            "requested action would capture raw private content",
            "requested action would perform an external write without an audit gate",
        ],
        **_outcome_provider_binding(connector_id),
    }


def _source_profiles() -> list[dict[str, Any]]:
    social_browser_x = build_social_browser_x_provider_packet()
    finance_migration = build_finance_extension_migration_contract()
    finance_profile = _source_profile(
        connector_id="finance_market_snapshot",
        status="migrated_to_extension",
        route_type="legacy extension migration",
        boundary="local_extension_migration",
        safe_uses=[
            "discover that the legacy connector moved to a standalone extension",
            "inspect exact provider installation, registration, and run preconditions",
            "stop when the separately distributed provider is unavailable",
        ],
        commands=[
            step["command"] for step in finance_migration["agent_start_sequence"]
        ],
        evidence_schema="finance_market_snapshot_probe_packet_v0",
        maturity_hint=(
            "Migration metadata only; this compatibility profile performs no "
            "finance reads and owns no Finance capability."
        ),
        stop_conditions=list(finance_migration["blocked_when"]),
    )
    finance_profile["migration"] = finance_migration
    return [
        _source_profile(
            connector_id="github_public_channel",
            status="implemented_starter",
            route_type="public metadata probe",
            boundary="public_metadata_only",
            safe_uses=[
                "validate public GitHub issue, PR, or discussion URLs",
                "collect allowlisted metadata such as title, state, count, and update time",
                "prepare demand or maintainer-interest evidence without copying body text",
            ],
            commands=[
                "loopx value-connectors github-public-probe --url <github-issue-or-pr-url> --format json",
                "loopx value-connectors github-public-probe --url <github-issue-or-pr-url> --fetch-metadata --format json",
            ],
            evidence_schema="github_public_channel_probe_packet_v0",
            maturity_hint="Use public metadata and maintainer/project fit; never infer intent from private body content.",
            stop_conditions=[
                "URL has query, fragment, auth material, or non-GitHub host",
                "the claim requires issue, PR, comment, or discussion body text",
                "the next action would comment, label, close, or mutate GitHub state",
            ],
        ),
        _source_profile(
            connector_id="github_public_reply_monitor",
            status="implemented_starter",
            route_type="public metadata monitor",
            boundary="public_metadata_only",
            safe_uses=[
                "detect public replies after a known LoopX comment anchor",
                "classify maintainer association metadata without comment bodies",
                "decide whether to prepare a public triage note or wait",
            ],
            commands=[
                "loopx value-connectors github-reply-monitor --issue-url <github-issue-or-pr-url> --after-comment-url <github-comment-url> --format json",
                "loopx value-connectors github-reply-monitor --issue-url <github-issue-or-pr-url> --after-comment-url <github-comment-url> --fetch-metadata --format json",
            ],
            evidence_schema="github_public_reply_monitor_packet_v0",
            maturity_hint="Treat maintainer/member replies after the anchor as stronger signal than generic public comments.",
            stop_conditions=[
                "anchor comment cannot be found",
                "provider payload contains raw body fields that would be copied forward",
                "agent would bump or reply to the thread without an exact gate",
            ],
        ),
        _source_profile(
            connector_id="content_ops_public_handle",
            status="implemented_starter",
            route_type="public handle observation",
            boundary="public_metadata_only",
            safe_uses=[
                "turn a public handle or profile URL into a compact source item",
                "start content-ops review from metadata before deeper connector reads",
                "record a no-fetch packet when the browser/account boundary is not ready",
            ],
            commands=[
                "loopx content-ops observe-public-handle --url <public-profile-url> --source-item-id <stable-source-id> --no-fetch --format json",
            ],
            evidence_schema="content_ops_public_handle_observation_packet_v0",
            maturity_hint="Use as a source-item anchor; require another source before making trend or demand claims.",
            stop_conditions=[
                "profile requires login-only body access",
                "the handle identity or account boundary is ambiguous",
                "the next step would scrape private timeline material",
            ],
        ),
        _source_profile(**social_browser_x["source_profile"]),
        _source_profile(
            connector_id="agent_reach_ops_source_map",
            status="field_derived_pattern",
            route_type="source router",
            boundary="route_specific_read_only",
            safe_uses=[
                "run connector doctor and choose available public/read-only routes",
                "collect public GitHub, web/RSS, V2EX, Bilibili, or similar signals into evidence cards",
                "score category maturity before drafting content",
            ],
            commands=[
                "agent-reach doctor --json",
                "loopx value-connectors source-map --connector agent_reach_ops_source_map --format json",
            ],
            evidence_schema="agent_reach_ops_signal_v0",
            maturity_hint="Score 0 noise, 1 weak, 2 emerging, 3 mature; corroborate source routes before drafting.",
            stop_conditions=[
                "doctor route is unavailable or boundary is unclear",
                "route needs cookies, private groups, DMs, captcha, or account setup",
                "draft would quote raw provider bodies beyond public-safe excerpts",
            ],
        ),
        finance_profile,
    ]


def _action_gated_profiles() -> list[dict[str, Any]]:
    return [
        {
            "connector_id": "botmail_identity",
            "boundary": "external_write_gated",
            "purpose": "email or botmail identity for replies and outreach",
            "safe_prepare_command": "loopx value-connectors plan --connector-id botmail_identity --connector-kind botmail_identity ... --format json",
            "write_gate": "exact sender, recipient, subject, body, metric, and stop condition required",
            **_outcome_provider_binding("botmail_identity"),
        },
        {
            "connector_id": "community_channel",
            "boundary": "external_write_gated",
            "purpose": "community reply or post after channel-rule review",
            "safe_prepare_command": "loopx value-connectors plan --connector-id community_channel --connector-kind community_channel ... --format json",
            "write_gate": "exact channel, account identity, message, value metric, and channel-rule fit required",
            **_outcome_provider_binding("community_channel"),
        },
    ]


def _generic_evidence_card_schema() -> dict[str, Any]:
    return {
        "schema_version": "connector_source_signal_v0",
        "connector_id": "<source profile id>",
        "channel": "github | x | web | rss | v2ex | bilibili | finance | other",
        "backend": "public-safe backend name",
        "query_or_target": "public-safe query, handle, symbol, URL, or topic",
        "title": "public-safe title or compact label",
        "url": "public URL or null",
        "summary": "one short public-safe summary of what the source supports",
        "boundary": "public_metadata_only | public_no_login | logged_in_read | route_specific_read_only",
        "operation": "read",
        "observed_at": "ISO-8601 timestamp",
        "confidence": "doctor_status | source_metadata | source_body_reviewed",
        "maturity_score": "0 | 1 | 2 | 3",
        "maturity_reason": "why the signal is noise, weak, emerging, or mature",
        "claims_supported": ["short claim this source can support"],
        "forbidden_next_actions": [
            "copy raw private body",
            "external write without publish/audit gate",
        ],
    }


def _maturity_scale() -> list[dict[str, Any]]:
    return [
        {"score": 0, "meaning": "noise or unavailable route"},
        {"score": 1, "meaning": "weak exploratory signal"},
        {"score": 2, "meaning": "emerging repeated signal"},
        {
            "score": 3,
            "meaning": "mature signal with strong adoption or multiple independent sources",
        },
    ]


def build_value_connector_source_map_packet(
    *, connector: str = "all"
) -> dict[str, Any]:
    if connector not in SOURCE_PROFILE_IDS:
        raise ValueError(f"unknown connector source map {connector!r}")
    profiles = [
        profile
        for profile in _source_profiles()
        if connector == "all" or profile["connector_id"] == connector
    ]
    action_gated = [] if connector != "all" else _action_gated_profiles()
    projection = {
        "schema_version": VALUE_CONNECTOR_SOURCE_MAP_PROJECTION_SCHEMA_VERSION,
        "agent_can_start_without_docs": True,
        "recommended_first_command": "loopx value-connectors source-map --format json",
        "source_profile_count": len(profiles),
        "action_gated_profile_count": len(action_gated),
        "external_write_blocked_by_default": True,
        "compatibility_facade": True,
        "new_profile_ownership_allowed": False,
        "mapped_profile_count": len(profiles) + len(action_gated),
        "migrated_profile_count": sum(
            1
            for profile in [*profiles, *action_gated]
            if profile.get("provider_binding_state") in {"migrated", "native"}
        ),
        "read_first_loop": [
            "choose source profile",
            "run only the read/metadata command",
            "emit connector_source_signal_v0 cards",
            "score maturity",
            "write ops brief or no-send packet",
            "use value-connectors plan before any external write",
        ],
    }
    return {
        "ok": True,
        "schema_version": VALUE_CONNECTOR_SOURCE_MAP_PACKET_SCHEMA_VERSION,
        "mode": "value-connectors-source-map",
        "connector": connector,
        "external_reads_performed": False,
        "external_writes_performed": False,
        "account_signup_performed": False,
        "restricted_material_recorded": False,
        "private_source_content_read": False,
        "autopublish_allowed": False,
        "source_profiles": profiles,
        "action_gated_profiles": action_gated,
        "generic_evidence_card_schema": _generic_evidence_card_schema(),
        "maturity_scale": _maturity_scale(),
        "projection": projection,
        "agent_prompt": (
            "Before drafting or posting from external signals, run `loopx "
            "value-connectors source-map --format json`, choose a read-only "
            "source profile, emit compact evidence cards, score maturity, and "
            "write an ops brief. Use `loopx value-connectors plan` for any "
            "signup, send, post, reply, upload, production action, credentialed "
            "read, or private-source expansion. Stop with a no-send packet when "
            "the active account, source boundary, body, or link state is unclear."
        ),
    }


def render_value_connector_source_map_markdown(payload: dict[str, Any]) -> str:
    projection = (
        payload.get("projection")
        if isinstance(payload.get("projection"), Mapping)
        else {}
    )
    lines = [
        "# LoopX Value Connector Source Map",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- connector: `{payload.get('connector')}`",
        f"- external_reads_performed: `{payload.get('external_reads_performed')}`",
        f"- external_writes_performed: `{payload.get('external_writes_performed')}`",
        f"- agent_can_start_without_docs: `{projection.get('agent_can_start_without_docs')}`",
        f"- compatibility_facade: `{projection.get('compatibility_facade')}`",
        f"- new_profile_ownership_allowed: `{projection.get('new_profile_ownership_allowed')}`",
        f"- source_profile_count: `{projection.get('source_profile_count')}`",
        f"- action_gated_profile_count: `{projection.get('action_gated_profile_count')}`",
        "",
        "## Read-First Loop",
        "",
    ]
    for step in projection.get("read_first_loop") or []:
        lines.append(f"- {step}")
    lines.extend(["", "## Source Profiles", ""])
    for profile in payload.get("source_profiles") or []:
        if not isinstance(profile, Mapping):
            continue
        lines.extend(
            [
                f"### `{profile.get('connector_id')}`",
                "",
                f"- status: `{profile.get('status')}`",
                f"- boundary: `{profile.get('boundary')}`",
            ]
        )
        if profile.get("outcome_capability_id"):
            lines.append(
                f"- outcome_capability_id: `{profile.get('outcome_capability_id')}`"
            )
        if profile.get("provider_binding_state"):
            lines.append(
                f"- provider_binding_state: `{profile.get('provider_binding_state')}`"
            )
        lines.extend(
            [
                f"- evidence_schema: `{profile.get('evidence_schema')}`",
                f"- maturity_hint: {profile.get('maturity_hint')}",
                "- commands:",
            ]
        )
        for command in profile.get("commands") or []:
            lines.append(f"  - `{command}`")
        migration = profile.get("migration")
        if isinstance(migration, Mapping):
            lines.extend(
                [
                    f"- replacement_extension_id: `{migration.get('replacement_extension_id')}`",
                    "- replacement_capability_id: `none`",
                    "- automatic_provider_install_supported: "
                    f"`{migration.get('automatic_provider_install_supported')}`",
                ]
            )
        if profile.get("write_gate"):
            lines.append(f"- write_gate: {profile.get('write_gate')}")
        lines.append("")
    action_gated = payload.get("action_gated_profiles")
    if isinstance(action_gated, list) and action_gated:
        lines.extend(["## Action-Gated Profiles", ""])
        for profile in action_gated:
            if not isinstance(profile, Mapping):
                continue
            lines.extend(
                [
                    f"- `{profile.get('connector_id')}`: {profile.get('purpose')}",
                    f"  - outcome_capability_id: `{profile.get('outcome_capability_id')}`",
                    f"  - provider_binding_state: `{profile.get('provider_binding_state')}`",
                    f"  - gate: {profile.get('write_gate')}",
                ]
            )
        lines.append("")
    lines.extend(["## Agent Prompt", "", str(payload.get("agent_prompt") or "")])
    return "\n".join(lines).rstrip() + "\n"
