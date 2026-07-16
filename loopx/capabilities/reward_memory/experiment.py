from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ...agent_registry import normalize_registered_agents
from ...control_plane.reward_memory import reward_memory_goal_policy
from ...control_plane.todos.contract import normalize_todo_claimed_by
from .application import normalize_reward_memory_provider_binding
from .ingestion import normalize_reward_memory_standing_policy
from .registry import MAX_CORPORA, normalize_reward_memory_corpus
from .scoped_feedback import SCOPED_FEEDBACK_ADAPTER


REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION = "reward_memory_experiment_config_v1"
REWARD_MEMORY_EXPERIMENT_V0_SCHEMA_VERSION = "reward_memory_experiment_config_v0"
ISSUE_FIX_MAINTAINER_FEEDBACK_ADAPTER = "issue_fix_maintainer_feedback"
SUPPORTED_REWARD_MEMORY_EXPERIMENT_ADAPTERS = {
    ISSUE_FIX_MAINTAINER_FEEDBACK_ADAPTER,
    SCOPED_FEEDBACK_ADAPTER,
}

_V0_CONFIG_FIELDS = {
    "schema_version",
    "adapter",
    "corpus",
    "standing_policy",
    "provider_binding",
}
_V1_CONFIG_FIELDS = {
    "schema_version",
    "project_provider_binding",
    "corpora",
    "surfaces",
    "automation",
}
_PROJECT_BINDING_FIELDS = {
    "provider_id",
    "namespace",
    "timeout_seconds",
    "setup_hints",
    "provider_binary",
    "minimum_provider_version",
    "actor_peer_id",
    "corpus_scopes",
}
_CORPUS_SCOPE_FIELDS = {"corpus_id", "scope_ref"}
_CORPUS_ENTRY_FIELDS = {"corpus", "standing_policy"}
_SURFACE_FIELDS = {
    "surface_id",
    "adapter",
    "corpus_ids",
    "ingest_corpus_id",
    "recall_profile",
}
_RECALL_PROFILE_FIELDS = {"profile_id", "mode", "max_queries", "limit"}
_AUTOMATION_FIELDS = {"automatic_recall", "automatic_ingest", "fail_open"}
_RECALL_MODES = {"function_boundary", "bounded_agentic_search"}


def _read_json_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def _strict_object(
    value: object, *, label: str, allowed: set[str]
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(unexpected)}")
    return value


def _bounded_objects(value: object, *, label: str, maximum: int) -> list[Mapping[str, Any]]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not 1 <= len(value) <= maximum
        or any(not isinstance(item, Mapping) for item in value)
    ):
        raise ValueError(f"{label} must be a bounded non-empty object list")
    return list(value)


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _positive_int(value: object, label: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{label} must be an integer between 1 and {maximum}")
    return value


def _adapter(value: object) -> str:
    result = str(value or "").strip()
    if result not in SUPPORTED_REWARD_MEMORY_EXPERIMENT_ADAPTERS:
        raise ValueError(
            "reward-memory experiment adapter must be one of: "
            + ", ".join(sorted(SUPPORTED_REWARD_MEMORY_EXPERIMENT_ADAPTERS))
        )
    return result


def _policy_matches_corpus(
    policy: Mapping[str, Any], corpus: Mapping[str, Any]
) -> bool:
    policy_scope = policy["scope"]
    corpus_scope = corpus["scope"]
    return (
        policy["owner_ref"] == corpus["owner_ref"]
        and policy_scope["workspace_ref"] == corpus_scope["workspace_ref"]
        and policy_scope["project_ref"] == corpus_scope["project_ref"]
        and set(policy_scope["surface_ids"]).issubset(corpus_scope["surface_ids"])
        and policy["allowed_target_classes"] == [corpus["class_id"]]
    )


def _compatibility_signature(
    corpus: Mapping[str, Any], policy: Mapping[str, Any]
) -> tuple[str, ...]:
    """Return the exact compatibility boundary for one surface corpus set."""

    return (
        str(corpus["class_id"]),
        str(corpus["owner_ref"]),
        str(corpus["read_authority"]),
        str(corpus["write_authority"]),
        str(policy["authority_source_ref"]),
        json.dumps(corpus["privacy"], sort_keys=True, separators=(",", ":")),
        json.dumps(corpus["freshness"], sort_keys=True, separators=(",", ":")),
        json.dumps(corpus["lifecycle"], sort_keys=True, separators=(",", ":")),
    )


def _materialize_provider_binding(
    project_binding: Mapping[str, Any],
    *,
    corpus: Mapping[str, Any],
    scope_ref: str,
) -> dict[str, Any]:
    raw = {
        key: project_binding[key]
        for key in (
            "provider_id",
            "namespace",
            "timeout_seconds",
            "setup_hints",
            "provider_binary",
            "minimum_provider_version",
            "actor_peer_id",
        )
        if key in project_binding
    }
    raw.update({"corpus_id": corpus["corpus_id"], "scope_ref": scope_ref})
    return normalize_reward_memory_provider_binding(raw, corpus)


def _normalize_v1(raw: Mapping[str, Any], *, source_schema: str) -> dict[str, Any]:
    _strict_object(raw, label="reward-memory experiment config", allowed=_V1_CONFIG_FIELDS)
    project_binding = _strict_object(
        raw.get("project_provider_binding"),
        label="project_provider_binding",
        allowed=_PROJECT_BINDING_FIELDS,
    )
    scopes = _bounded_objects(
        project_binding.get("corpus_scopes"),
        label="project_provider_binding.corpus_scopes",
        maximum=MAX_CORPORA,
    )
    scope_refs: dict[str, str] = {}
    for index, item in enumerate(scopes):
        scope = _strict_object(
            item,
            label=f"project_provider_binding.corpus_scopes[{index}]",
            allowed=_CORPUS_SCOPE_FIELDS,
        )
        corpus_id = str(scope.get("corpus_id") or "").strip()
        scope_ref = str(scope.get("scope_ref") or "").strip()
        if not corpus_id or not scope_ref:
            raise ValueError("each project provider corpus scope must be exact")
        if corpus_id in scope_refs:
            raise ValueError("project provider corpus scopes must not contain duplicates")
        scope_refs[corpus_id] = scope_ref

    raw_corpora = _bounded_objects(
        raw.get("corpora"), label="corpora", maximum=MAX_CORPORA
    )
    corpora: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw_corpora):
        entry = _strict_object(
            item, label=f"corpora[{index}]", allowed=_CORPUS_ENTRY_FIELDS
        )
        corpus_raw = entry.get("corpus")
        policy_raw = entry.get("standing_policy")
        if not isinstance(corpus_raw, Mapping) or not isinstance(policy_raw, Mapping):
            raise ValueError("each corpus entry requires corpus and standing_policy")
        corpus = normalize_reward_memory_corpus(corpus_raw)
        policy = normalize_reward_memory_standing_policy(policy_raw)
        corpus_id = corpus["corpus_id"]
        if corpus_id in corpora:
            raise ValueError("corpora must not contain duplicate corpus ids")
        if not _policy_matches_corpus(policy, corpus):
            raise ValueError(
                "standing policy authority and scope must stay inside its corpus"
            )
        if corpus["provider_id"] != project_binding.get("provider_id"):
            raise ValueError("every corpus must use the project provider binding")
        corpora[corpus_id] = {
            "corpus": corpus,
            "standing_policy": policy,
        }

    if set(scope_refs) != set(corpora):
        raise ValueError("project provider corpus scopes must exactly match declared corpora")
    workspace_projects = {
        (
            entry["corpus"]["scope"]["workspace_ref"],
            entry["corpus"]["scope"]["project_ref"],
        )
        for entry in corpora.values()
    }
    if len(workspace_projects) != 1:
        raise ValueError("all corpora must belong to one exact project scope")
    for corpus_id, entry in corpora.items():
        entry["provider_binding"] = _materialize_provider_binding(
            project_binding,
            corpus=entry["corpus"],
            scope_ref=scope_refs[corpus_id],
        )

    raw_surfaces = _bounded_objects(
        raw.get("surfaces"), label="surfaces", maximum=20
    )
    surfaces: dict[str, dict[str, Any]] = {}
    referenced_corpora: set[str] = set()
    for index, item in enumerate(raw_surfaces):
        surface = _strict_object(
            item, label=f"surfaces[{index}]", allowed=_SURFACE_FIELDS
        )
        surface_id = str(surface.get("surface_id") or "").strip()
        if not surface_id or surface_id in surfaces:
            raise ValueError("surface_id must be present and unique")
        corpus_ids_raw = surface.get("corpus_ids")
        if (
            not isinstance(corpus_ids_raw, Sequence)
            or isinstance(corpus_ids_raw, (str, bytes))
            or not 1 <= len(corpus_ids_raw) <= MAX_CORPORA
        ):
            raise ValueError("surface.corpus_ids must be a bounded non-empty list")
        corpus_ids = [str(value or "").strip() for value in corpus_ids_raw]
        if any(not value for value in corpus_ids) or len(corpus_ids) != len(set(corpus_ids)):
            raise ValueError("surface.corpus_ids must contain unique corpus ids")
        unknown = sorted(set(corpus_ids) - set(corpora))
        if unknown:
            raise ValueError("surface selects an undeclared corpus: " + ", ".join(unknown))
        ingest_corpus_id = str(surface.get("ingest_corpus_id") or "").strip()
        if ingest_corpus_id not in corpus_ids:
            raise ValueError("surface.ingest_corpus_id must be one selected corpus")
        for corpus_id in corpus_ids:
            if surface_id not in corpora[corpus_id]["corpus"]["scope"]["surface_ids"]:
                raise ValueError("surface must be declared by every selected corpus")
            if surface_id not in (
                corpora[corpus_id]["standing_policy"]["scope"]["surface_ids"]
            ):
                raise ValueError(
                    "surface must be authorized by every selected standing policy"
                )
        signatures = {
            _compatibility_signature(
                corpora[corpus_id]["corpus"],
                corpora[corpus_id]["standing_policy"],
            )
            for corpus_id in corpus_ids
        }
        if len(signatures) != 1:
            raise ValueError(
                "surface corpora must share memory class, authority, privacy, freshness, and lifecycle"
            )
        profile = _strict_object(
            surface.get("recall_profile"),
            label=f"surfaces[{index}].recall_profile",
            allowed=_RECALL_PROFILE_FIELDS,
        )
        mode = str(profile.get("mode") or "").strip()
        if mode not in _RECALL_MODES:
            raise ValueError("recall_profile.mode is unsupported")
        profile_id = str(profile.get("profile_id") or "").strip()
        if not profile_id:
            raise ValueError("recall_profile.profile_id must be present")
        surfaces[surface_id] = {
            "surface_id": surface_id,
            "adapter": _adapter(surface.get("adapter")),
            "corpus_ids": corpus_ids,
            "ingest_corpus_id": ingest_corpus_id,
            "recall_profile": {
                "profile_id": profile_id,
                "mode": mode,
                "max_queries": _positive_int(
                    profile.get("max_queries"),
                    "recall_profile.max_queries",
                    maximum=3,
                ),
                "limit": _positive_int(
                    profile.get("limit"), "recall_profile.limit", maximum=8
                ),
            },
        }
        referenced_corpora.update(corpus_ids)
    if referenced_corpora != set(corpora):
        raise ValueError("every declared corpus must be assigned to an explicit surface")

    automation = _strict_object(
        raw.get("automation"), label="automation", allowed=_AUTOMATION_FIELDS
    )
    fail_open = _boolean(automation.get("fail_open"), "automation.fail_open")
    if not fail_open:
        raise ValueError("reward-memory automation must be fail-open")
    normalized = {
        "schema_version": REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION,
        "source_schema_version": source_schema,
        "migration_applied": source_schema == REWARD_MEMORY_EXPERIMENT_V0_SCHEMA_VERSION,
        "project_provider_binding": {
            key: value
            for key, value in project_binding.items()
            if key != "corpus_scopes"
        },
        "corpora": corpora,
        "surfaces": surfaces,
        "automation": {
            "automatic_recall": _boolean(
                automation.get("automatic_recall"), "automation.automatic_recall"
            ),
            "automatic_ingest": _boolean(
                automation.get("automatic_ingest"), "automation.automatic_ingest"
            ),
            "fail_open": True,
        },
    }
    if len(surfaces) == 1:
        route = resolve_reward_memory_surface_config(
            normalized, next(iter(surfaces))
        )
        normalized.update(
            {
                "adapter": route["adapter"],
                "corpus": route["corpus"],
                "standing_policy": route["standing_policy"],
                "provider_binding": route["provider_binding"],
            }
        )
    return normalized


def _migrate_v0(raw: Mapping[str, Any]) -> dict[str, Any]:
    _strict_object(raw, label="reward-memory experiment config", allowed=_V0_CONFIG_FIELDS)
    for key in ("corpus", "standing_policy", "provider_binding"):
        if not isinstance(raw.get(key), Mapping):
            raise ValueError(f"reward-memory experiment {key} must be an object")
    corpus = normalize_reward_memory_corpus(raw["corpus"])
    binding = normalize_reward_memory_provider_binding(raw["provider_binding"], corpus)
    surfaces = list(
        normalize_reward_memory_standing_policy(raw["standing_policy"])["scope"][
            "surface_ids"
        ]
    )
    common_binding = {
        key: binding[key]
        for key in (
            "provider_id",
            "namespace",
            "timeout_seconds",
            "setup_hints",
            "provider_binary",
            "minimum_provider_version",
            "actor_peer_id",
        )
        if key in binding
    }
    common_binding["corpus_scopes"] = [
        {"corpus_id": corpus["corpus_id"], "scope_ref": binding["scope_ref"]}
    ]
    migrated = {
        "schema_version": REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION,
        "project_provider_binding": common_binding,
        "corpora": [
            {
                "corpus": raw["corpus"],
                "standing_policy": raw["standing_policy"],
            }
        ],
        "surfaces": [
            {
                "surface_id": surface_id,
                "adapter": _adapter(raw.get("adapter")),
                "corpus_ids": [corpus["corpus_id"]],
                "ingest_corpus_id": corpus["corpus_id"],
                "recall_profile": {
                    "profile_id": f"v0_explicit_{surface_id.replace('.', '_')}",
                    "mode": "function_boundary",
                    "max_queries": 1,
                    "limit": 5,
                },
            }
            for surface_id in surfaces
        ],
        "automation": {
            "automatic_recall": False,
            "automatic_ingest": False,
            "fail_open": True,
        },
    }
    return _normalize_v1(
        migrated, source_schema=REWARD_MEMORY_EXPERIMENT_V0_SCHEMA_VERSION
    )


def load_reward_memory_experiment_config(
    *, project: Path, config_path: str
) -> dict[str, Any]:
    path = project / config_path
    try:
        raw = _read_json_object(path)
    except (OSError, ValueError) as exc:
        raise ValueError("reward-memory experiment config is unavailable") from exc
    schema_version = raw.get("schema_version")
    if schema_version == REWARD_MEMORY_EXPERIMENT_V0_SCHEMA_VERSION:
        return _migrate_v0(raw)
    if schema_version == REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION:
        return _normalize_v1(raw, source_schema=REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION)
    raise ValueError(
        "reward-memory experiment config must use reward_memory_experiment_config_v0 or v1"
    )


def resolve_reward_memory_surface_config(
    config: Mapping[str, Any],
    surface_id: str,
    *,
    adapter: str | None = None,
) -> dict[str, Any]:
    """Select only the corpora explicitly assigned to one module surface."""

    surfaces = config.get("surfaces")
    corpora = config.get("corpora")
    if not isinstance(surfaces, Mapping) or not isinstance(corpora, Mapping):
        raise ValueError("reward-memory config is not normalized")
    surface = surfaces.get(surface_id)
    if not isinstance(surface, Mapping):
        raise ValueError("reward-memory surface is not configured")
    configured_adapter = str(surface.get("adapter") or "")
    if adapter and adapter != configured_adapter:
        raise ValueError("input adapter does not match the configured route")
    routes: list[dict[str, Any]] = []
    for corpus_id in surface.get("corpus_ids") or []:
        entry = corpora.get(corpus_id)
        if not isinstance(entry, Mapping):
            raise ValueError("configured surface corpus is unavailable")
        routes.append(
            {
                "corpus": entry["corpus"],
                "standing_policy": entry["standing_policy"],
                "provider_binding": entry["provider_binding"],
            }
        )
    ingest_id = str(surface.get("ingest_corpus_id") or "")
    ingest = next(
        (route for route in routes if route["corpus"]["corpus_id"] == ingest_id),
        None,
    )
    if ingest is None:
        raise ValueError("configured ingest corpus is unavailable")
    return {
        "schema_version": "reward_memory_surface_config_v0",
        "surface_id": surface_id,
        "adapter": configured_adapter,
        "recall_profile": dict(surface["recall_profile"]),
        "recall_corpora": routes,
        "selection": {
            "mode": "explicit_surface_corpus_ids",
            "global_corpus_scan": False,
            "corpus_ids": list(surface["corpus_ids"]),
        },
        "corpus": ingest["corpus"],
        "standing_policy": ingest["standing_policy"],
        "provider_binding": ingest["provider_binding"],
    }


def resolve_reward_memory_experiment(
    *, registry_path: Path, goal_id: str, agent_id: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve an agent-scoped experiment without exposing local config details."""

    normalized_agent = normalize_todo_claimed_by(agent_id)
    if not normalized_agent:
        raise ValueError("agent_id must be a public-safe registered agent id")
    registry = _read_json_object(registry_path)
    goals = registry.get("goals") if isinstance(registry.get("goals"), list) else []
    goal = next(
        (
            item
            for item in goals
            if isinstance(item, Mapping) and str(item.get("id")) == goal_id
        ),
        None,
    )
    if goal is None:
        raise ValueError(f"goal_id not found in registry: {goal_id}")
    registered_agents = normalize_registered_agents(
        (goal.get("coordination") or {}).get("registered_agents")
        if isinstance(goal.get("coordination"), Mapping)
        else None
    )
    if normalized_agent not in registered_agents:
        raise ValueError(f"agent_id is not registered for goal {goal_id}")
    policy = reward_memory_goal_policy(goal)
    base = {
        "ok": True,
        "schema_version": "reward_memory_experiment_status_v1",
        "goal_id": goal_id,
        "agent_id": normalized_agent,
        "experimental": policy["experimental"],
        "enabled": policy["enabled"],
        "configured_for_agent": normalized_agent in policy["enabled_agents"],
        "config_pointer_registered": bool(policy["config_path"]),
        "automatic_ingest": False,
        "automatic_recall": False,
        "fail_open": True,
        "external_writes_performed": False,
    }
    if not policy["enabled"]:
        return base | {"status": "disabled", "available": False}, None
    if normalized_agent not in policy["enabled_agents"]:
        return base | {"status": "agent_not_enabled", "available": False}, None
    if not policy["config_path"]:
        return base | {"status": "config_missing", "available": False}, None
    project = Path(str(goal.get("repo") or "")).expanduser()
    try:
        config = load_reward_memory_experiment_config(
            project=project,
            config_path=policy["config_path"],
        )
    except ValueError:
        return base | {
            "status": "config_invalid",
            "available": False,
            "reason_code": "config_unavailable_or_invalid",
        }, None
    corpora = config["corpora"]
    surfaces = config["surfaces"]
    automation = config["automation"]
    result = base | {
        "status": "available",
        "available": True,
        "source_config_schema_version": config["source_schema_version"],
        "effective_config_schema_version": config["schema_version"],
        "migration_applied": config["migration_applied"],
        "provider_id": config["project_provider_binding"]["provider_id"],
        "corpus_count": len(corpora),
        "corpus_ids": sorted(corpora),
        "surface_ids": sorted(surfaces),
        "surface_profiles": [
            {
                "surface_id": surface_id,
                "adapter": surface["adapter"],
                "corpus_count": len(surface["corpus_ids"]),
                "recall_profile_id": surface["recall_profile"]["profile_id"],
            }
            for surface_id, surface in sorted(surfaces.items())
        ],
        "automatic_ingest": automation["automatic_ingest"],
        "automatic_recall": automation["automatic_recall"],
        "fail_open": automation["fail_open"],
        "raw_content_captured": False,
    }
    if len(surfaces) == 1:
        route = resolve_reward_memory_surface_config(config, next(iter(surfaces)))
        result.update(
            {
                "adapter": route["adapter"],
                "corpus_id": route["corpus"]["corpus_id"],
            }
        )
    return result, config
