from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any


QUALITY_SURFACE_CATALOG_SCHEMA_VERSION = "quality_surface_catalog_v0"
QUALITY_SURFACE_AUDIT_SCHEMA_VERSION = "quality_surface_catalog_audit_v0"

QUALITY_LAYER_IDS = (
    "unit_contract",
    "durable_smoke",
    "catalog_canary",
    "host_upgrade",
    "model_behavior",
    "release_gate",
)
DETERMINISTIC_MINIMUM_LAYERS = (
    "unit_contract",
    "durable_smoke",
    "catalog_canary",
)
_LAYER_STATUSES = {"covered", "not_applicable", "deferred"}
_ORACLE_SOURCE_KINDS = {
    "external_standard",
    "metamorphic_rule",
    "reviewed_invariant",
    "specification",
}


def _covered(*refs: str) -> dict[str, Any]:
    return {"status": "covered", "refs": list(refs)}


def _not_applicable(rationale: str) -> dict[str, Any]:
    return {"status": "not_applicable", "rationale": rationale}


def _deferred(*, owner: str, rationale: str) -> dict[str, Any]:
    return {"status": "deferred", "owner": owner, "rationale": rationale}


QUALITY_SURFACE_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "surface_id": "interaction-scheduler-authority",
        "title": "Interaction contract and scheduler authority",
        "risk": "high",
        "canary_profile_id": "control-plane-state-machine",
        "owner_paths": [
            "loopx/control_plane/scheduler/arbitration.py",
            "loopx/control_plane/todos/decision_scope.py",
            "loopx/control_plane/work_items/interaction_contract.py",
        ],
        "semantic_oracle": {
            "source_kind": "metamorphic_rule",
            "refs": [
                "tests/fixtures/control_plane/public_safe_decision_replay_v0.json"
            ],
            "independence_rationale": (
                "Reviewed source facts and precedence invariants define the expected "
                "decision; lower-level should-run fields are mutated independently of "
                "the production scheduler."
            ),
        },
        "layers": {
            "unit_contract": _covered(
                "tests/control_plane/test_scheduler_interaction_arbitration.py",
                "tests/control_plane/test_todo_decision_scope_consistency.py",
                "tests/control_plane/test_public_safe_decision_replay.py",
            ),
            "durable_smoke": _covered(
                "examples/control_plane/interaction-scheduler-authority-smoke.py"
            ),
            "catalog_canary": _covered("control-plane-state-machine"),
            "host_upgrade": _not_applicable(
                "The precedence rule is host-independent and is exercised before host scheduling."
            ),
            "model_behavior": _not_applicable(
                "A stochastic actor must not decide deterministic scheduler precedence."
            ),
            "release_gate": _covered(
                "loopx canary premerge --profile control-plane-state-machine"
            ),
        },
    },
    {
        "surface_id": "scheduler-ack-route",
        "title": "Scheduler ACK state and route binding",
        "risk": "high",
        "canary_profile_id": "scheduler-ack-route",
        "owner_paths": [
            "loopx/control_plane/quota/live_decision.py",
            "loopx/control_plane/scheduler/ack.py",
            "loopx/control_plane/scheduler/state.py",
        ],
        "semantic_oracle": {
            "source_kind": "specification",
            "refs": ["docs/status-data-contract.md"],
            "independence_rationale": (
                "The status contract requires ACK arguments to retain the registry and "
                "effective runtime-root route that emitted the scheduler hint, independently "
                "of the binding and persistence implementations."
            ),
        },
        "layers": {
            "unit_contract": _covered(
                "tests/test_loopx_turn_driver.py",
                "tests/control_plane/test_scheduler_ack_decision_table.py",
                "tests/control_plane/test_scheduler_backoff_convergence.py",
            ),
            "durable_smoke": _covered(
                "examples/control_plane/quota-scheduler-state-ack-smoke.py",
                "examples/control_plane/quota-scheduler-registry-route-smoke.py",
            ),
            "catalog_canary": _covered("scheduler-ack-route"),
            "host_upgrade": _not_applicable(
                "The host executes bound CLI arguments but does not choose or rewrite their registry route."
            ),
            "model_behavior": _not_applicable(
                "Route binding and ACK state progression are deterministic safety invariants."
            ),
            "release_gate": _covered(
                "loopx canary premerge --profile scheduler-ack-route"
            ),
        },
    },
    {
        "surface_id": "goal-frontier-replan",
        "title": "Goal-frontier replan obligation and precedence",
        "risk": "high",
        "canary_profile_id": "goal-frontier-replan-rules",
        "owner_paths": [
            "loopx/control_plane/goals/goal_frontier.py",
            "loopx/control_plane/goals/goal_frontier_replan_rules.py",
            "loopx/control_plane/work_items/autonomous_replan_ack.py",
        ],
        "semantic_oracle": {
            "source_kind": "specification",
            "refs": [
                "docs/reference/protocols/goal-vision-replan-contract-v0.md"
            ],
            "independence_rationale": (
                "The goal-vision contract defines when an agent-local frontier is "
                "exhausted, blocked, or already advancing before the ordered rule "
                "selector and quota projection are exercised."
            ),
        },
        "layers": {
            "unit_contract": _covered(
                "tests/control_plane/test_goal_frontier_replan_rules.py",
                "tests/control_plane/test_goal_vision_succession.py",
                "tests/control_plane/test_goal_vision_blocked_successor.py",
            ),
            "durable_smoke": _covered(
                "examples/control_plane/goal-frontier-replan-rules-smoke.py",
                "examples/control_plane/quota-replan-decision-plane-smoke.py",
            ),
            "catalog_canary": _covered("goal-frontier-replan-rules"),
            "host_upgrade": _not_applicable(
                "Host continuity does not decide whether an agent-local goal frontier requires replanning."
            ),
            "model_behavior": _not_applicable(
                "Replan precedence is a deterministic control-plane invariant, not a model judgment."
            ),
            "release_gate": _covered(
                "loopx canary premerge --profile goal-frontier-replan-rules"
            ),
        },
    },
    {
        "surface_id": "agent-facing-cli-output",
        "title": "Agent-facing guided projection and output budgets",
        "risk": "high",
        "canary_profile_id": "agent-facing-cli-output-budget",
        "owner_paths": [
            "loopx/bootstrap_command_pack.py",
            "loopx/control_plane/testing/cli_output_budget.py",
            "loopx/control_plane/quota/turn_envelope.py",
        ],
        "semantic_oracle": {
            "source_kind": "specification",
            "refs": ["docs/interface-budget-contract.md"],
            "independence_rationale": (
                "The interface contract names required actions and semantic anchors; "
                "current stdout is measured against that contract rather than copied into a golden."
            ),
        },
        "layers": {
            "unit_contract": _covered(
                "tests/control_plane/test_cli_output_budget.py",
                "tests/control_plane/test_cli_output_differential.py",
                "tests/control_plane/test_start_goal_compact_projection.py",
            ),
            "durable_smoke": _covered(
                "examples/control_plane/cli-output-budget-regression-smoke.py"
            ),
            "catalog_canary": _covered("agent-facing-cli-output-budget"),
            "host_upgrade": _not_applicable(
                "Host activation and upgrade continuity are owned by the onboarding and install surfaces."
            ),
            "model_behavior": _covered(
                "actual_default_model_behavior_portfolio_v0",
                "onboarding_actual_behavior_qualification_v0"
            ),
            "release_gate": _covered(
                "loopx canary premerge --profile agent-facing-cli-output-budget"
            ),
        },
    },
    {
        "surface_id": "release-promotion",
        "title": "Exact-source release promotion",
        "risk": "high",
        "canary_profile_id": "release-promotion",
        "owner_paths": [
            "loopx/control_plane/runtime/promotion_readiness.py",
            "loopx/control_plane/testing/release_commit_qualification.py",
            "loopx/promotion_gate.py",
            "loopx/release_manifest.py",
        ],
        "semantic_oracle": {
            "source_kind": "specification",
            "refs": ["docs/product/release-readiness.md"],
            "independence_rationale": (
                "Promotion requirements are declared before a candidate run and bind evidence "
                "to source identity instead of accepting the latest generated receipt."
            ),
        },
        "layers": {
            "unit_contract": _covered(
                "tests/control_plane/test_release_commit_qualification.py",
                "tests/control_plane/test_release_outcome_baseline.py",
                "tests/test_doctor_install_freshness.py",
            ),
            "durable_smoke": _covered(
                "examples/canary/canary-promotion-readiness-smoke.py",
                "examples/release/exact-release-commit-qualification-smoke.py",
            ),
            "catalog_canary": _covered("release-promotion"),
            "host_upgrade": _covered(
                "examples/release/release-version-contract-smoke.py"
            ),
            "model_behavior": _covered(
                "actual_default_model_behavior_portfolio_v0"
            ),
            "release_gate": _covered(
                "loopx canary premerge --profile release-promotion",
                "loopx canary release-qualification",
            ),
        },
    },
    {
        "surface_id": "install-update-safety",
        "title": "Install and update safety",
        "risk": "high",
        "canary_profile_id": "install-update",
        "owner_paths": [
            "loopx/self_update.py",
            "scripts/install-from-github.sh",
            "scripts/install-local.sh",
        ],
        "semantic_oracle": {
            "source_kind": "specification",
            "refs": ["docs/product/codex-cli-packaged-install.md"],
            "independence_rationale": (
                "The packaged-install contract defines provenance, rollback, and no-system-mutation "
                "requirements independently of installer output."
            ),
        },
        "layers": {
            "unit_contract": _covered(
                "tests/test_doctor_install_freshness.py",
                "tests/test_slash_command_install.py",
            ),
            "durable_smoke": _covered("examples/install-local-smoke.py"),
            "catalog_canary": _covered("install-update"),
            "host_upgrade": _covered("examples/loopx-update-smoke.py"),
            "model_behavior": _not_applicable(
                "Installer correctness is deterministic and must not depend on model interpretation."
            ),
            "release_gate": _covered("loopx canary premerge --profile install-update"),
        },
    },
    {
        "surface_id": "state-write-correctness",
        "title": "State and todo write correctness",
        "risk": "high",
        "canary_profile_id": "state-write-correctness",
        "owner_paths": [
            "loopx/state_refresh.py",
            "loopx/todos.py",
            "loopx/control_plane/runtime",
        ],
        "semantic_oracle": {
            "source_kind": "reviewed_invariant",
            "refs": ["docs/product/core-control-plane/state-machine.md"],
            "independence_rationale": (
                "Lifecycle invariants define legal revisions, ownership, and idempotency before "
                "writer implementations are exercised."
            ),
        },
        "layers": {
            "unit_contract": _covered("tests/control_plane/test_task_lease.py"),
            "durable_smoke": _covered(
                "examples/control_plane/refresh-state-write-correctness-smoke.py",
                "examples/control_plane/todo-write-correctness-smoke.py",
            ),
            "catalog_canary": _covered("state-write-correctness"),
            "host_upgrade": _not_applicable(
                "Host continuity does not change the state writer's atomicity and lifecycle rules."
            ),
            "model_behavior": _not_applicable(
                "State mutation safety is a deterministic contract, not a model judgment."
            ),
            "release_gate": _covered(
                "loopx canary premerge --profile state-write-correctness"
            ),
        },
    },
    {
        "surface_id": "new-user-onboarding",
        "title": "New-user goal start and host activation",
        "risk": "high",
        "canary_profile_id": "new-user-onboarding-lifecycle",
        "owner_paths": [
            "loopx/agent_onboarding.py",
            "loopx/bootstrap_command_pack.py",
            "loopx/host_loop_activation.py",
        ],
        "semantic_oracle": {
            "source_kind": "specification",
            "refs": [
                "docs/reference/protocols/model-behavior-qualification-v0.md"
            ],
            "independence_rationale": (
                "The onboarding contract specifies identity, goal selection, command, and host "
                "activation outcomes before the actual default packet is shown to the actor."
            ),
        },
        "layers": {
            "unit_contract": _covered(
                "tests/control_plane/test_goal_start_control_score.py",
                "tests/control_plane/test_start_goal_compact_projection.py",
                "tests/control_plane/test_onboarding_model_behavior_qualification.py",
            ),
            "durable_smoke": _covered(
                "examples/project/onboarding-no-scan-projection-smoke.py"
            ),
            "catalog_canary": _covered("new-user-onboarding-lifecycle"),
            "host_upgrade": _covered(
                "examples/control_plane/agent-onboard-host-loop-activation-smoke.py"
            ),
            "model_behavior": _covered(
                "actual_default_model_behavior_portfolio_v0",
                "onboarding_actual_behavior_qualification_v0"
            ),
            "release_gate": _covered(
                "loopx canary premerge --profile new-user-onboarding-lifecycle"
            ),
        },
    },
    {
        "surface_id": "peer-agent-runtime",
        "title": "Peer identity, claims, leases, and continuation",
        "risk": "high",
        "canary_profile_id": "peer-agent-runtime",
        "owner_paths": [
            "loopx/control_plane/agents",
            "loopx/control_plane/quota/task_orchestration.py",
            "loopx/control_plane/todos/completion_policy.py",
        ],
        "semantic_oracle": {
            "source_kind": "specification",
            "refs": ["docs/reference/protocols/peer-agent-runtime-v1.md"],
            "independence_rationale": (
                "The rank-free ownership and continuation protocol defines legal routing before "
                "the quota and workspace implementations are evaluated."
            ),
        },
        "layers": {
            "unit_contract": _covered(
                "tests/control_plane/test_task_lease.py",
                "tests/control_plane/test_user_gate_lane_progress.py",
            ),
            "durable_smoke": _covered(
                "examples/control_plane/peer-agent-runtime-v1-smoke.py"
            ),
            "catalog_canary": _covered("peer-agent-runtime"),
            "host_upgrade": _covered(
                "examples/project/configure-goal-global-sync-smoke.py"
            ),
            "model_behavior": _covered(
                "actual_default_model_behavior_portfolio_v0",
                "turn_peer_agent_identity",
                "turn_same_agent_continuation",
            ),
            "release_gate": _covered("loopx canary premerge --profile peer-agent-runtime"),
        },
    },
)


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _repo_path_ref(value: str) -> str | None:
    if " " in value or not value.startswith(
        ("docs/", "examples/", "loopx/", "scripts/", "tests/")
    ):
        return None
    return value.split("#", 1)[0]


def build_quality_surface_catalog_audit(
    domain_profiles: Iterable[Mapping[str, Any]],
    *,
    catalog: Iterable[Mapping[str, Any]] = QUALITY_SURFACE_CATALOG,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    profiles = [dict(profile) for profile in domain_profiles]
    high_risk_profile_ids = sorted(
        str(profile.get("id") or "")
        for profile in profiles
        if profile.get("quality_risk") == "high" and profile.get("id")
    )
    entries = [deepcopy(dict(entry)) for entry in catalog]
    profile_ids = {str(profile.get("id") or "") for profile in profiles}
    entry_ids = [str(entry.get("surface_id") or "") for entry in entries]
    entry_profile_ids = [str(entry.get("canary_profile_id") or "") for entry in entries]

    drift: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    layer_counts: dict[str, Counter[str]] = {
        layer_id: Counter() for layer_id in QUALITY_LAYER_IDS
    }

    for surface_id, count in Counter(entry_ids).items():
        if not surface_id or count > 1:
            drift.append(
                {
                    "code": "duplicate_or_missing_surface_id",
                    "surface_id": surface_id or None,
                    "count": count,
                }
            )
    for profile_id, count in Counter(entry_profile_ids).items():
        if not profile_id or count > 1:
            drift.append(
                {
                    "code": "duplicate_or_missing_canary_profile_id",
                    "canary_profile_id": profile_id or None,
                    "count": count,
                }
            )

    classified_profile_ids = set(entry_profile_ids)
    for profile_id in high_risk_profile_ids:
        if profile_id not in classified_profile_ids:
            drift.append(
                {
                    "code": "unclassified_high_risk_profile",
                    "canary_profile_id": profile_id,
                }
            )

    high_risk_set = set(high_risk_profile_ids)
    for entry in entries:
        surface_id = str(entry.get("surface_id") or "")
        profile_id = str(entry.get("canary_profile_id") or "")
        if profile_id not in profile_ids:
            drift.append(
                {
                    "code": "unknown_canary_profile",
                    "surface_id": surface_id,
                    "canary_profile_id": profile_id,
                }
            )
        elif profile_id not in high_risk_set:
            drift.append(
                {
                    "code": "catalog_profile_not_marked_high_risk",
                    "surface_id": surface_id,
                    "canary_profile_id": profile_id,
                }
            )

        owner_paths = _text_list(entry.get("owner_paths"))
        if not owner_paths:
            drift.append({"code": "missing_owner_paths", "surface_id": surface_id})
        if repo_root is not None:
            for owner_path in owner_paths:
                if not (repo_root / owner_path).exists():
                    drift.append(
                        {
                            "code": "missing_repository_reference",
                            "surface_id": surface_id,
                            "ref": owner_path,
                            "ref_role": "owner_path",
                        }
                    )

        oracle = entry.get("semantic_oracle")
        oracle_map = dict(oracle) if isinstance(oracle, Mapping) else {}
        oracle_kind = str(oracle_map.get("source_kind") or "")
        oracle_refs = _text_list(oracle_map.get("refs"))
        if oracle_kind not in _ORACLE_SOURCE_KINDS:
            drift.append(
                {
                    "code": "invalid_or_implementation_derived_oracle",
                    "surface_id": surface_id,
                    "source_kind": oracle_kind or None,
                }
            )
        if not oracle_refs or not str(
            oracle_map.get("independence_rationale") or ""
        ).strip():
            drift.append(
                {"code": "incomplete_semantic_oracle", "surface_id": surface_id}
            )
        overlap = sorted(set(owner_paths) & set(oracle_refs))
        if overlap:
            drift.append(
                {
                    "code": "circular_oracle_uses_product_source",
                    "surface_id": surface_id,
                    "refs": overlap,
                }
            )
        if repo_root is not None:
            for oracle_ref in oracle_refs:
                repo_ref = _repo_path_ref(oracle_ref)
                if repo_ref and not (repo_root / repo_ref).exists():
                    drift.append(
                        {
                            "code": "missing_repository_reference",
                            "surface_id": surface_id,
                            "ref": oracle_ref,
                            "ref_role": "semantic_oracle",
                        }
                    )

        raw_layers = entry.get("layers")
        layers = dict(raw_layers) if isinstance(raw_layers, Mapping) else {}
        unknown_layers = sorted(set(layers) - set(QUALITY_LAYER_IDS))
        if unknown_layers:
            drift.append(
                {
                    "code": "unknown_quality_layers",
                    "surface_id": surface_id,
                    "layers": unknown_layers,
                }
            )
        evidence_layers: defaultdict[str, list[str]] = defaultdict(list)
        for layer_id in QUALITY_LAYER_IDS:
            raw_layer = layers.get(layer_id)
            layer = dict(raw_layer) if isinstance(raw_layer, Mapping) else {}
            status = str(layer.get("status") or "")
            layer_counts[layer_id][status or "missing"] += 1
            if status not in _LAYER_STATUSES:
                drift.append(
                    {
                        "code": "missing_or_invalid_layer_status",
                        "surface_id": surface_id,
                        "layer": layer_id,
                    }
                )
                continue
            refs = _text_list(layer.get("refs"))
            rationale = str(layer.get("rationale") or "").strip()
            owner = str(layer.get("owner") or "").strip()
            if status == "covered":
                if not refs:
                    drift.append(
                        {
                            "code": "covered_layer_has_no_evidence",
                            "surface_id": surface_id,
                            "layer": layer_id,
                        }
                    )
                for ref in refs:
                    evidence_layers[ref].append(layer_id)
                    repo_ref = _repo_path_ref(ref)
                    if (
                        repo_root is not None
                        and repo_ref
                        and not (repo_root / repo_ref).exists()
                    ):
                        drift.append(
                            {
                                "code": "missing_repository_reference",
                                "surface_id": surface_id,
                                "ref": ref,
                                "ref_role": layer_id,
                            }
                        )
            elif status == "not_applicable" and not rationale:
                drift.append(
                    {
                        "code": "not_applicable_without_rationale",
                        "surface_id": surface_id,
                        "layer": layer_id,
                    }
                )
            elif status == "deferred":
                if not rationale or not owner:
                    drift.append(
                        {
                            "code": "deferred_without_owner_or_rationale",
                            "surface_id": surface_id,
                            "layer": layer_id,
                        }
                    )
                else:
                    gaps.append(
                        {
                            "code": "deferred_quality_layer",
                            "surface_id": surface_id,
                            "layer": layer_id,
                            "owner": owner,
                            "rationale": rationale,
                        }
                    )

        for required_layer in DETERMINISTIC_MINIMUM_LAYERS:
            required_layer_value = layers.get(required_layer)
            required_status = (
                required_layer_value.get("status")
                if isinstance(required_layer_value, Mapping)
                else None
            )
            if required_status != "covered":
                drift.append(
                    {
                        "code": "high_risk_deterministic_minimum_missing",
                        "surface_id": surface_id,
                        "layer": required_layer,
                    }
                )
        canary_layer = layers.get("catalog_canary")
        canary_refs = (
            _text_list(canary_layer.get("refs"))
            if isinstance(canary_layer, Mapping)
            else []
        )
        if profile_id and profile_id not in canary_refs:
            drift.append(
                {
                    "code": "catalog_canary_profile_mismatch",
                    "surface_id": surface_id,
                    "canary_profile_id": profile_id,
                }
            )
        for ref, layer_ids in sorted(evidence_layers.items()):
            if len(layer_ids) > 1:
                drift.append(
                    {
                        "code": "duplicate_evidence_across_layers",
                        "surface_id": surface_id,
                        "ref": ref,
                        "layers": layer_ids,
                    }
                )

    normalized_layer_counts = {
        layer_id: dict(sorted(counts.items()))
        for layer_id, counts in layer_counts.items()
    }
    return {
        "ok": not drift,
        "ready": not drift and not gaps,
        "schema_version": QUALITY_SURFACE_AUDIT_SCHEMA_VERSION,
        "catalog_schema_version": QUALITY_SURFACE_CATALOG_SCHEMA_VERSION,
        "dry_run": True,
        "executes_checks": False,
        "repository_reference_validation": (
            "performed" if repo_root is not None else "source_checkout_unavailable"
        ),
        "high_risk_profile_count": len(high_risk_profile_ids),
        "classified_surface_count": len(entries),
        "drift_count": len(drift),
        "gap_count": len(gaps),
        "high_risk_profile_ids": high_risk_profile_ids,
        "layer_counts": normalized_layer_counts,
        "drift": drift,
        "gaps": gaps,
        "surfaces": entries,
        "note": (
            "Every high-risk canary profile must have one independently sourced semantic "
            "oracle and an explicit classification for every quality layer. Covered, "
            "not-applicable, and deferred are different states: model and host tests are "
            "required only when their semantics apply."
        ),
    }


def render_quality_surface_catalog_audit_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Quality Surface Catalog Audit",
        "",
        f"- high_risk_profiles: `{payload.get('high_risk_profile_count')}`",
        f"- classified_surfaces: `{payload.get('classified_surface_count')}`",
        f"- drift: `{payload.get('drift_count')}`",
        f"- deferred_gaps: `{payload.get('gap_count')}`",
        f"- ready: `{str(bool(payload.get('ready'))).lower()}`",
        "- repository_reference_validation: "
        f"`{payload.get('repository_reference_validation')}`",
        "- dry_run: `true`",
        "- executes_checks: `false`",
        "",
        str(payload.get("note") or ""),
        "",
    ]
    if payload.get("drift"):
        lines.extend(["## Drift", ""])
        for item in payload.get("drift", []):
            if isinstance(item, Mapping):
                lines.append(
                    f"- `{item.get('code')}` surface=`{item.get('surface_id')}`"
                )
        lines.append("")
    if payload.get("gaps"):
        lines.extend(["## Deferred Gaps", ""])
        for item in payload.get("gaps", []):
            if isinstance(item, Mapping):
                lines.append(
                    f"- `{item.get('surface_id')}` / `{item.get('layer')}`: "
                    f"{item.get('rationale')} (owner: `{item.get('owner')}`)"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
