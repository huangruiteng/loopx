from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Literal

from ..quota.turn_envelope import (
    ACTION_SIGNATURE_COVERAGE_V0,
    ACTION_SIGNATURE_COVERAGE_V1,
    ACTION_SIGNATURE_COVERAGE_V2,
    ACTION_SIGNATURE_COVERAGE_V3,
    ACTION_SIGNATURE_COVERAGE_V4,
)


CLI_OUTPUT_PROBE_SCHEMA_VERSION = "loopx_cli_output_probe_v0"
CLI_OUTPUT_FIXTURE_CONTRACT_VERSION = "loopx_cli_output_public_fixture_v0"
CLI_OUTPUT_DIFFERENTIAL_SCHEMA_VERSION = "loopx_cli_output_differential_v0"
ACTION_PORTFOLIO_SCHEMA_VERSION_V0 = "quota_action_portfolio_v0"
ACTION_PORTFOLIO_SCHEMA_VERSION_V1 = "quota_action_portfolio_v1"
ACTION_PORTFOLIO_SCHEMA_VERSION_V2 = "quota_action_portfolio_v2"
PLANNING_HORIZON_SCHEMA_VERSION_V0 = "quota_planning_horizon_v0"
GUIDED_TODO_DELTA_SCHEMA_VERSION_V0 = "loopx_guided_todo_delta_v0"
PLANNING_INVENTORY_DETAIL_SCHEMA_VERSION_V0 = (
    "todo_planning_inventory_detail_v0"
)

Metric = Literal["chars", "utf8_bytes", "lines", "compact_payload_chars"]


def select_cli_output_base_ref(
    requested_ref: str,
    *,
    main_ref: str,
    is_ancestor: Callable[[str, str], bool],
) -> str:
    """Choose main for a sync commit that brings main into a stale PR base."""
    if requested_ref == main_ref:
        return requested_ref
    head_contains_main = is_ancestor(main_ref, "HEAD")
    requested_contains_main = is_ancestor(main_ref, requested_ref)
    if head_contains_main and not requested_contains_main:
        return main_ref
    return requested_ref


@dataclass(frozen=True)
class GrowthAllowance:
    ratio: float
    json: dict[Metric, int]
    markdown: dict[Metric, int]


_GROWTH_ALLOWANCE_BY_POLICY: dict[str, GrowthAllowance] = {
    "absolute_hot_path": GrowthAllowance(
        ratio=0.005,
        json={"chars": 64, "utf8_bytes": 128, "lines": 2, "compact_payload_chars": 64},
        markdown={
            "chars": 32,
            "utf8_bytes": 64,
            "lines": 1,
            "compact_payload_chars": 0,
        },
    ),
    "baseline_and_growth": GrowthAllowance(
        ratio=0.005,
        json={
            "chars": 128,
            "utf8_bytes": 256,
            "lines": 2,
            "compact_payload_chars": 128,
        },
        markdown={
            "chars": 64,
            "utf8_bytes": 128,
            "lines": 1,
            "compact_payload_chars": 0,
        },
    ),
    "explicit_limit_cold_path": GrowthAllowance(
        ratio=0.01,
        json={
            "chars": 256,
            "utf8_bytes": 512,
            "lines": 5,
            "compact_payload_chars": 256,
        },
        markdown={
            "chars": 128,
            "utf8_bytes": 256,
            "lines": 2,
            "compact_payload_chars": 0,
        },
    ),
    "explicit_opt_in_cold_path": GrowthAllowance(
        ratio=0.01,
        json={
            "chars": 256,
            "utf8_bytes": 512,
            "lines": 5,
            "compact_payload_chars": 256,
        },
        markdown={
            "chars": 128,
            "utf8_bytes": 256,
            "lines": 2,
            "compact_payload_chars": 0,
        },
    ),
}

# quota_action_portfolio_v1/v2 migrations add a bounded executable portfolio
# and then inline the small action context needed to interpret each choice.
# This allowance applies only to a declared schema transition; once v2 is the
# baseline, ordinary policy budgets apply again.
_ACTION_PORTFOLIO_V0_MIGRATION_GROWTH_ALLOWANCE: dict[Metric, int] = {
    "chars": 1_600,
    "utf8_bytes": 1_600,
    "lines": 42,
    "compact_payload_chars": 1_280,
}

# quota_planning_horizon_v0 adds one bounded read-only strategic context to the
# default agent path and TurnEnvelope. This allowance applies only while the
# schema and action-signature coverage move to v0/v3; after merge the candidate
# becomes the new baseline and ordinary growth limits apply again.
_PLANNING_HORIZON_V0_MIGRATION_GROWTH_ALLOWANCE: dict[Metric, int] = {
    "chars": 3_200,
    "utf8_bytes": 3_200,
    "lines": 84,
    "compact_payload_chars": 2_800,
}

# Capability-owned context adds one bounded signed planning contribution. Only
# an explicit older-coverage -> v4 transition receives this allowance; v4 -> v4
# keeps the ordinary output budget. Absolute probe ceilings remain unchanged.
_AGENT_CONTEXT_V4_MIGRATION_GROWTH_ALLOWANCE: dict[Metric, int] = {
    "chars": 2_048,
    "utf8_bytes": 2_048,
    "lines": 48,
    "compact_payload_chars": 1_664,
}

# todo_planning_inventory_detail_v0 adds planning/claim semantics only to the
# explicit agent-Todo detail variants. The allowance is bound to the declared
# none-to-v0 schema migration; after merge the ordinary cold-path budget
# applies again.
_PLANNING_INVENTORY_DETAIL_V0_MIGRATION_GROWTH_ALLOWANCE: dict[Metric, int] = {
    "chars": 1_280,
    "utf8_bytes": 1_280,
    "lines": 36,
    "compact_payload_chars": 1_024,
}

# Explicit runtime-root command routing repeats one bounded command prefix per
# executable action. The allowance covers the prefix and its JSON projection;
# it is per newly observed route, not per row, so unrelated output growth still
# fails under the normal hot-path policy.
_RUNTIME_ROOT_COMMAND_ROUTE_GROWTH_PER_ROUTE: dict[Metric, int] = {
    "chars": 160,
    "utf8_bytes": 160,
    "lines": 0,
    "compact_payload_chars": 160,
}

# loopx_guided_todo_delta_v0 adds the continuation-aware Todo authoring
# decision contract (reuse/update/link_successor/add_new plus a bounded
# runnable-frontier summary) to the guided start-goal packet when an
# existing-Agent takeover is projected. The allowance is bound to the
# declared none-to-v0 schema migration; after merge the ordinary
# start_goal_guided growth budgets apply again.
_GUIDED_TODO_DELTA_V0_MIGRATION_GROWTH_ALLOWANCE: dict[Metric, int] = {
    "chars": 512,
    "utf8_bytes": 512,
    "lines": 16,
    "compact_payload_chars": 448,
}


def _runtime_root_route_growth_allowances(
    base: dict[str, Any], candidate: dict[str, Any]
) -> tuple[int, dict[Metric, int]]:
    base_routes = base.get("runtime_root_command_route_count")
    candidate_routes = candidate.get("runtime_root_command_route_count")
    if type(base_routes) is not int or type(candidate_routes) is not int:
        return 0, {}
    added_routes = max(0, candidate_routes - base_routes)
    if not added_routes:
        return 0, {}
    return added_routes, {
        metric: added_routes * allowance
        for metric, allowance in _RUNTIME_ROOT_COMMAND_ROUTE_GROWTH_PER_ROUTE.items()
    }


def _rows_by_id(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if receipt.get("schema_version") != CLI_OUTPUT_PROBE_SCHEMA_VERSION:
        raise ValueError("CLI output probe receipt has an unsupported schema_version")
    if receipt.get("fixture_contract_version") != CLI_OUTPUT_FIXTURE_CONTRACT_VERSION:
        raise ValueError(
            "CLI output probe receipt has an unsupported fixture_contract_version"
        )
    rows = receipt.get("rows")
    if not isinstance(rows, list):
        raise ValueError("CLI output probe receipt rows must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("row_id"), str):
            raise ValueError("CLI output probe row must be an object with row_id")
        row_id = row["row_id"]
        if row_id in indexed:
            raise ValueError(f"duplicate CLI output probe row_id: {row_id}")
        indexed[row_id] = row
    return indexed


def _growth_limit(*, policy: str, output_format: str, metric: Metric, base: int) -> int:
    allowance = _GROWTH_ALLOWANCE_BY_POLICY.get(policy)
    if allowance is None:
        raise ValueError(f"unsupported CLI output qualification policy: {policy}")
    floors = allowance.json if output_format == "json" else allowance.markdown
    return max(floors[metric], math.ceil(base * allowance.ratio))


def _removed(base: dict[str, Any], candidate: dict[str, Any], field: str) -> list[str]:
    base_values = {str(value) for value in base.get(field, [])}
    candidate_values = {str(value) for value in candidate.get(field, [])}
    return sorted(base_values - candidate_values)


def _action_signature_migration(
    base: dict[str, Any], candidate: dict[str, Any]
) -> str | None:
    base_coverages = base.get("action_signature_coverages")
    candidate_coverages = candidate.get("action_signature_coverages")
    allowed_migrations = {
        (ACTION_SIGNATURE_COVERAGE_V0, ACTION_SIGNATURE_COVERAGE_V1),
        (ACTION_SIGNATURE_COVERAGE_V0, ACTION_SIGNATURE_COVERAGE_V2),
        (ACTION_SIGNATURE_COVERAGE_V1, ACTION_SIGNATURE_COVERAGE_V2),
        (ACTION_SIGNATURE_COVERAGE_V0, ACTION_SIGNATURE_COVERAGE_V3),
        (ACTION_SIGNATURE_COVERAGE_V1, ACTION_SIGNATURE_COVERAGE_V3),
        (ACTION_SIGNATURE_COVERAGE_V2, ACTION_SIGNATURE_COVERAGE_V3),
        (ACTION_SIGNATURE_COVERAGE_V0, ACTION_SIGNATURE_COVERAGE_V4),
        (ACTION_SIGNATURE_COVERAGE_V1, ACTION_SIGNATURE_COVERAGE_V4),
        (ACTION_SIGNATURE_COVERAGE_V2, ACTION_SIGNATURE_COVERAGE_V4),
        (ACTION_SIGNATURE_COVERAGE_V3, ACTION_SIGNATURE_COVERAGE_V4),
    }
    if not (
        isinstance(base_coverages, list)
        and len(base_coverages) == 1
        and isinstance(candidate_coverages, list)
        and len(candidate_coverages) == 1
    ):
        return None
    migration = (base_coverages[0], candidate_coverages[0])
    if migration not in allowed_migrations:
        return None
    return f"{migration[0]} -> {migration[1]}"


def _action_portfolio_schema_migration(
    base: dict[str, Any], candidate: dict[str, Any]
) -> str | None:
    base_versions = base.get("action_portfolio_schema_versions")
    candidate_versions = candidate.get("action_portfolio_schema_versions")
    allowed_migrations = {
        ((), (ACTION_PORTFOLIO_SCHEMA_VERSION_V0,)),
        ((), (ACTION_PORTFOLIO_SCHEMA_VERSION_V1,)),
        ((), (ACTION_PORTFOLIO_SCHEMA_VERSION_V2,)),
        (
            (ACTION_PORTFOLIO_SCHEMA_VERSION_V0,),
            (ACTION_PORTFOLIO_SCHEMA_VERSION_V1,),
        ),
        (
            (ACTION_PORTFOLIO_SCHEMA_VERSION_V0,),
            (ACTION_PORTFOLIO_SCHEMA_VERSION_V2,),
        ),
        (
            (ACTION_PORTFOLIO_SCHEMA_VERSION_V1,),
            (ACTION_PORTFOLIO_SCHEMA_VERSION_V2,),
        ),
    }
    migration = (tuple(base_versions or []), tuple(candidate_versions or []))
    if migration in allowed_migrations:
        before = base_versions[0] if base_versions else "none"
        after = candidate_versions[0] if candidate_versions else "none"
        return f"{before} -> {after}"
    return None


def _planning_horizon_schema_migration(
    base: dict[str, Any], candidate: dict[str, Any]
) -> str | None:
    base_versions = tuple(base.get("planning_horizon_schema_versions") or [])
    candidate_versions = tuple(
        candidate.get("planning_horizon_schema_versions") or []
    )
    if base_versions == () and candidate_versions == (
        PLANNING_HORIZON_SCHEMA_VERSION_V0,
    ):
        return f"none -> {PLANNING_HORIZON_SCHEMA_VERSION_V0}"
    return None


def _guided_todo_delta_schema_migration(
    base: dict[str, Any], candidate: dict[str, Any]
) -> str | None:
    base_versions = tuple(base.get("guided_todo_delta_schema_versions") or [])
    candidate_versions = tuple(
        candidate.get("guided_todo_delta_schema_versions") or []
    )
    if base_versions == () and candidate_versions == (
        GUIDED_TODO_DELTA_SCHEMA_VERSION_V0,
    ):
        return f"none -> {GUIDED_TODO_DELTA_SCHEMA_VERSION_V0}"
    return None


def _planning_inventory_detail_schema_migration(
    base: dict[str, Any], candidate: dict[str, Any]
) -> str | None:
    base_versions = tuple(
        base.get("planning_inventory_detail_schema_versions") or []
    )
    candidate_versions = tuple(
        candidate.get("planning_inventory_detail_schema_versions") or []
    )
    if base_versions == () and candidate_versions == (
        PLANNING_INVENTORY_DETAIL_SCHEMA_VERSION_V0,
    ):
        return f"none -> {PLANNING_INVENTORY_DETAIL_SCHEMA_VERSION_V0}"
    return None


@dataclass(frozen=True)
class _SchemaMigrationState:
    signature_changed: bool
    signature_migration: str | None
    portfolio_schema_changed: bool
    portfolio_schema_migration: str | None
    horizon_schema_changed: bool
    horizon_schema_migration: str | None
    inventory_detail_schema_changed: bool
    inventory_detail_schema_migration: str | None
    guided_todo_delta_schema_changed: bool
    guided_todo_delta_schema_migration: str | None
    portfolio_growth_migration: bool
    horizon_growth_migration: bool
    agent_context_growth_migration: bool
    inventory_detail_growth_migration: bool
    guided_todo_delta_growth_migration: bool


def _schema_migration_state(
    base: dict[str, Any], candidate: dict[str, Any], *, output_format: str
) -> _SchemaMigrationState:
    base_signature = base.get("action_signature_sha256")
    signature_changed = bool(
        base_signature
        and candidate.get("action_signature_sha256") != base_signature
    )
    signature_migration = (
        _action_signature_migration(base, candidate) if signature_changed else None
    )
    base_portfolio_versions = base.get("action_portfolio_schema_versions")
    candidate_portfolio_versions = candidate.get("action_portfolio_schema_versions")
    portfolio_schema_changed = base_portfolio_versions != candidate_portfolio_versions
    portfolio_schema_migration = (
        _action_portfolio_schema_migration(base, candidate)
        if portfolio_schema_changed
        else None
    )
    base_horizon_versions = base.get("planning_horizon_schema_versions")
    candidate_horizon_versions = candidate.get("planning_horizon_schema_versions")
    horizon_schema_changed = base_horizon_versions != candidate_horizon_versions
    horizon_schema_migration = (
        _planning_horizon_schema_migration(base, candidate)
        if horizon_schema_changed
        else None
    )
    base_inventory_detail_versions = base.get(
        "planning_inventory_detail_schema_versions"
    )
    candidate_inventory_detail_versions = candidate.get(
        "planning_inventory_detail_schema_versions"
    )
    inventory_detail_schema_changed = (
        base_inventory_detail_versions != candidate_inventory_detail_versions
    )
    inventory_detail_schema_migration = (
        _planning_inventory_detail_schema_migration(base, candidate)
        if inventory_detail_schema_changed
        else None
    )
    guided_todo_delta_schema_changed = (
        tuple(base.get("guided_todo_delta_schema_versions") or [])
        != tuple(candidate.get("guided_todo_delta_schema_versions") or [])
    )
    guided_todo_delta_schema_migration = (
        _guided_todo_delta_schema_migration(base, candidate)
        if guided_todo_delta_schema_changed
        else None
    )
    return _SchemaMigrationState(
        signature_changed=signature_changed,
        signature_migration=signature_migration,
        portfolio_schema_changed=portfolio_schema_changed,
        portfolio_schema_migration=portfolio_schema_migration,
        horizon_schema_changed=horizon_schema_changed,
        horizon_schema_migration=horizon_schema_migration,
        inventory_detail_schema_changed=inventory_detail_schema_changed,
        inventory_detail_schema_migration=inventory_detail_schema_migration,
        guided_todo_delta_schema_changed=guided_todo_delta_schema_changed,
        guided_todo_delta_schema_migration=guided_todo_delta_schema_migration,
        portfolio_growth_migration=bool(
            output_format == "json"
            and (
                portfolio_schema_migration
                or (
                    signature_migration
                    and signature_migration.endswith(
                        f" -> {ACTION_SIGNATURE_COVERAGE_V2}"
                    )
                )
            )
        ),
        horizon_growth_migration=bool(
            output_format == "json"
            and (
                horizon_schema_migration
                or (
                    signature_migration
                    and signature_migration.endswith(
                        f" -> {ACTION_SIGNATURE_COVERAGE_V3}"
                    )
                )
            )
        ),
        agent_context_growth_migration=bool(
            output_format == "json"
            and signature_migration
            and signature_migration.endswith(f" -> {ACTION_SIGNATURE_COVERAGE_V4}")
        ),
        inventory_detail_growth_migration=bool(
            output_format == "json" and inventory_detail_schema_migration
        ),
        guided_todo_delta_growth_migration=bool(
            output_format == "json" and guided_todo_delta_schema_migration
        ),
    )


def _compare_row(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    row_id = str(base["row_id"])
    failures: list[str] = []
    review_signals: list[str] = []
    policy = str(base.get("qualification_policy") or "")
    output_format = str(base.get("format") or "")
    if candidate.get("qualification_policy") != policy:
        failures.append("qualification_policy changed")
    if candidate.get("format") != output_format:
        failures.append("format changed")

    migration = _schema_migration_state(
        base,
        candidate,
        output_format=output_format,
    )
    added_runtime_root_routes, runtime_root_route_allowances = (
        _runtime_root_route_growth_allowances(base, candidate)
    )

    deltas: dict[str, int | None] = {}
    allowances: dict[str, int | None] = {}
    for metric in ("chars", "utf8_bytes", "lines", "compact_payload_chars"):
        base_value = base.get(metric)
        candidate_value = candidate.get(metric)
        if not isinstance(base_value, int) or not isinstance(candidate_value, int):
            deltas[metric] = None
            allowances[metric] = None
            continue
        delta = candidate_value - base_value
        allowance = _growth_limit(
            policy=policy,
            output_format=output_format,
            metric=metric,
            base=base_value,
        )
        # Thin installed prompts contain bilingual lifecycle instructions. A
        # small character-level clarification can cost three bytes per CJK
        # character. Keep character, line and absolute output ceilings intact;
        # do not relax quota or other agent-facing surfaces with this allowance.
        if row_id.startswith("surface/heartbeat_prompt_thin/") and metric == "utf8_bytes":
            allowance = max(allowance, 192)
        if (row_id.startswith(("surface/", "variant/"))
                and row_id.partition("/")[2].partition("/")[0] in {
                    "heartbeat_prompt_thin", "heartbeat_prompt_brief", "heartbeat_prompt_compact"}
                and base.get("host_prompt_static_safety_revision") is None
                and candidate.get("host_prompt_static_safety_revision") == "host_prompt_static_safety_v1"):
            # Authorized static safety + executable shell bootstrap restoration.
            # Absolute ceilings stay enforced by the probe; once merged, v1->v1
            # receives no allowance. Quota/status and other surfaces are excluded.
            allowance = max(allowance, {"chars": 512, "utf8_bytes": 640,
                                       "lines": 5, "compact_payload_chars": 512}[metric])
        if migration.portfolio_growth_migration:
            allowance = max(
                allowance,
                _ACTION_PORTFOLIO_V0_MIGRATION_GROWTH_ALLOWANCE[metric],
            )
        if migration.horizon_growth_migration:
            allowance = max(
                allowance,
                _PLANNING_HORIZON_V0_MIGRATION_GROWTH_ALLOWANCE[metric],
            )
        if migration.agent_context_growth_migration:
            allowance = max(
                allowance, _AGENT_CONTEXT_V4_MIGRATION_GROWTH_ALLOWANCE[metric]
            )
        if migration.inventory_detail_growth_migration:
            allowance = max(
                allowance,
                _PLANNING_INVENTORY_DETAIL_V0_MIGRATION_GROWTH_ALLOWANCE[
                    metric
                ],
            )
        if migration.guided_todo_delta_growth_migration:
            allowance = max(
                allowance,
                _GUIDED_TODO_DELTA_V0_MIGRATION_GROWTH_ALLOWANCE[metric],
            )
        if runtime_root_route_allowances:
            allowance = max(
                allowance,
                runtime_root_route_allowances[metric],
            )
        deltas[metric] = delta
        allowances[metric] = allowance
        if delta > allowance:
            failures.append(f"{metric} grew by {delta}; allowance is {allowance}")

    for field in ("semantic_json_keys",):
        missing = _removed(base, candidate, field)
        if missing:
            preview = ", ".join(missing[:5])
            suffix = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            failures.append(f"{field} removed: {preview}{suffix}")

    for field in ("json_shape_paths", "markdown_headings"):
        missing = _removed(base, candidate, field)
        if missing:
            preview = ", ".join(missing[:5])
            suffix = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
            review_signals.append(f"{field} removed: {preview}{suffix}")

    base_anchor = base.get("markdown_anchor")
    if base_anchor and candidate.get("markdown_anchor") != base_anchor:
        failures.append("markdown_anchor changed")
    if migration.signature_changed:
        if migration.signature_migration is None:
            failures.append("action_signature semantic digest changed")
        else:
            review_signals.append(
                f"action_signature coverage migrated: {migration.signature_migration}"
            )
    if migration.portfolio_schema_changed:
        if migration.portfolio_schema_migration is None:
            failures.append("action_portfolio schema coverage changed")
        else:
            review_signals.append(
                "action_portfolio schema migrated: "
                f"{migration.portfolio_schema_migration}"
            )
    if migration.horizon_schema_changed:
        if migration.horizon_schema_migration is None:
            failures.append("planning_horizon schema coverage changed")
        else:
            review_signals.append(
                "planning_horizon schema migrated: "
                f"{migration.horizon_schema_migration}"
            )
    if migration.inventory_detail_schema_changed:
        if migration.inventory_detail_schema_migration is None:
            failures.append("planning inventory detail schema coverage changed")
        else:
            review_signals.append(
                "planning inventory detail schema migrated: "
                f"{migration.inventory_detail_schema_migration}"
            )
    if runtime_root_route_allowances:
        review_signals.append(
            "runtime-root command route coverage added: "
            f"{added_runtime_root_routes} executable route(s)"
        )
    if migration.guided_todo_delta_schema_changed:
        if migration.guided_todo_delta_schema_migration is None:
            failures.append("guided todo delta schema coverage changed")
        else:
            review_signals.append(
                "guided todo delta schema migrated: "
                f"{migration.guided_todo_delta_schema_migration}"
            )

    return {
        "row_id": row_id,
        "status": "failed" if failures else "passed",
        "deltas": deltas,
        "allowances": allowances,
        "failures": failures,
        "review_signals": review_signals,
    }


def compare_cli_output_receipts(
    base_receipt: dict[str, Any],
    candidate_receipt: dict[str, Any],
) -> dict[str, Any]:
    base_rows = _rows_by_id(base_receipt)
    candidate_rows = _rows_by_id(candidate_receipt)
    results: list[dict[str, Any]] = []
    for row_id in sorted(base_rows.keys() | candidate_rows.keys()):
        base = base_rows.get(row_id)
        candidate = candidate_rows.get(row_id)
        if base is None:
            results.append(
                {
                    "row_id": row_id,
                    "status": "candidate_only",
                    "deltas": {},
                    "allowances": {},
                    "failures": [],
                    "review_signals": [],
                }
            )
        elif candidate is None:
            results.append(
                {
                    "row_id": row_id,
                    "status": "failed",
                    "deltas": {},
                    "allowances": {},
                    "failures": ["qualified base row is missing from candidate"],
                    "review_signals": [],
                }
            )
        else:
            results.append(_compare_row(base, candidate))

    failed_rows = [row for row in results if row["status"] == "failed"]
    review_rows = [row for row in results if row["review_signals"]]
    return {
        "schema_version": CLI_OUTPUT_DIFFERENTIAL_SCHEMA_VERSION,
        "ok": not failed_rows,
        "base_row_count": len(base_rows),
        "candidate_row_count": len(candidate_rows),
        "compared_row_count": len(results),
        "failed_row_count": len(failed_rows),
        "review_required": bool(review_rows),
        "review_row_count": len(review_rows),
        "candidate_only_row_count": sum(
            row["status"] == "candidate_only" for row in results
        ),
        "rows": results,
    }
