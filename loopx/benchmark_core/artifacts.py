from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


BENCHMARK_PUBLIC_ARTIFACT_SUFFIXES = (
    ".compact.json",
    ".public.json",
)
BENCHMARK_PUBLIC_ARTIFACT_FILENAMES = (
    "paired_comparison.compact.json",
    "launch_status.public.json",
    "launch_summaries.public.json",
    "loopx-active-user-observation.json",
)
BENCHMARK_RAW_PRIVATE_PATH_MARKERS = (
    "/agent/trajectory.json",
    "/sessions/",
    "/logs/",
    "/raw/",
    "trajectory.json",
    "origin_log",
    "instruction.md",
    "task.md",
    "/screenshots/",
    "screenshot",
)
BENCHMARK_PRIVATE_MANIFEST_SUFFIXES = (
    ".local.json",
    ".private.json",
)
BENCHMARK_ARTIFACT_POLICY_REGISTRY: dict[str, dict[str, tuple[str, ...]]] = {
    "default": {
        "public_suffixes": BENCHMARK_PUBLIC_ARTIFACT_SUFFIXES,
        "public_filenames": BENCHMARK_PUBLIC_ARTIFACT_FILENAMES,
        "raw_private_markers": BENCHMARK_RAW_PRIVATE_PATH_MARKERS,
        "private_suffixes": BENCHMARK_PRIVATE_MANIFEST_SUFFIXES,
    },
    "terminal-bench": {
        "public_suffixes": BENCHMARK_PUBLIC_ARTIFACT_SUFFIXES,
        "public_filenames": BENCHMARK_PUBLIC_ARTIFACT_FILENAMES,
        "raw_private_markers": BENCHMARK_RAW_PRIVATE_PATH_MARKERS,
        "private_suffixes": BENCHMARK_PRIVATE_MANIFEST_SUFFIXES,
    },
    "agents-last-exam": {
        "public_suffixes": BENCHMARK_PUBLIC_ARTIFACT_SUFFIXES,
        "public_filenames": (
            "agents-last-exam-local-preflight.json",
            "agents-last-exam-local-dry-run-plan.json",
            "agents-last-exam-local-runner-readiness.json",
            "agents-last-exam-local-source-readiness.json",
            "agents-last-exam-task-material-readiness.json",
            "agents-last-exam-baked-task-input-readiness.json",
            "agents-last-exam-baked-task-input-scan.json",
            "agents-last-exam-candidate-task-data-scan.json",
            "agents-last-exam-local-launch-packet.json",
            "agents-last-exam-local-exact-dry-run-result.json",
            "agents-last-exam-host-codex-cli-route.json",
            "agents-last-exam-host-codex-cua-no-task-smoke.json",
            "agents-last-exam-validation-run-gate.json",
        ),
        "raw_private_markers": (
            "trajectory.json",
            "origin_log",
            "/output/",
            "/outputs/",
            "/screenshots/",
            "screenshot",
            "hidden_refs",
            "credentials",
            "instruction.md",
            "task.md",
        ),
        "private_suffixes": BENCHMARK_PRIVATE_MANIFEST_SUFFIXES,
    },
}


def _safe_artifact_policy_key(adapter_kind: str | None) -> str:
    key = str(adapter_kind or "default").strip().lower().replace("_", "-")
    if key in BENCHMARK_ARTIFACT_POLICY_REGISTRY:
        return key
    return "default"


def _safe_public_artifact_basename(value: Any) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    basename = str(value).replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
    if not basename or basename in {".", ".."}:
        return ""
    if basename.endswith(BENCHMARK_PRIVATE_MANIFEST_SUFFIXES):
        return ""
    if any(marker in basename for marker in ("trajectory", "credential", "secret")):
        return ""
    return basename


def _benchmark_artifact_policy(
    *,
    adapter_kind: str | None = None,
    extra_public_filenames: Iterable[Any] = (),
) -> dict[str, Any]:
    policy_key = _safe_artifact_policy_key(adapter_kind)
    default_policy = BENCHMARK_ARTIFACT_POLICY_REGISTRY["default"]
    policy = BENCHMARK_ARTIFACT_POLICY_REGISTRY[policy_key]
    filenames = set(default_policy["public_filenames"])
    filenames.update(policy["public_filenames"])
    filenames.update(
        basename
        for basename in (
            _safe_public_artifact_basename(value)
            for value in extra_public_filenames
        )
        if basename
    )
    return {
        "adapter_kind": policy_key,
        "public_suffixes": tuple(
            sorted(set(default_policy["public_suffixes"]) | set(policy["public_suffixes"]))
        ),
        "public_filenames": tuple(sorted(filenames)),
        "raw_private_markers": tuple(
            sorted(
                set(default_policy["raw_private_markers"])
                | set(policy["raw_private_markers"])
            )
        ),
        "private_suffixes": tuple(
            sorted(
                set(default_policy["private_suffixes"])
                | set(policy["private_suffixes"])
            )
        ),
    }


def classify_benchmark_artifact_path(
    path: str | Path,
    *,
    adapter_kind: str | None = None,
    extra_public_filenames: Iterable[Any] = (),
) -> dict[str, Any]:
    """Classify a benchmark artifact path without echoing host directories."""

    policy = _benchmark_artifact_policy(
        adapter_kind=adapter_kind,
        extra_public_filenames=extra_public_filenames,
    )
    normalized = str(path).replace("\\", "/").rstrip("/")
    basename = normalized.rsplit("/", 1)[-1] if normalized else ""
    lower_path = normalized.lower()
    lower_basename = basename.lower()
    public_compact_candidate = (
        lower_basename.endswith(policy["public_suffixes"])
        or lower_basename in policy["public_filenames"]
    )
    raw_marker = next(
        (marker for marker in policy["raw_private_markers"] if marker in lower_path),
        "",
    )
    private_manifest = lower_basename.endswith(policy["private_suffixes"])

    allowed_to_read = (
        public_compact_candidate
        and not raw_marker
        and not private_manifest
    )
    if allowed_to_read:
        first_blocker = ""
        recommended_action = "read only this compact/public artifact, then ingest its reduced fields"
    elif raw_marker:
        first_blocker = "raw_private_surface"
        recommended_action = "do not read; use a compact/public sibling artifact or runner-side reducer"
    elif private_manifest:
        first_blocker = "private_or_local_manifest"
        recommended_action = "do not read; summarize via a public compact launch summary instead"
    else:
        first_blocker = "not_compact_public_artifact"
        recommended_action = "skip unless a benchmark-specific reducer explicitly whitelists it"

    return {
        "schema_version": "benchmark_artifact_path_classification_v0",
        "path_recorded": False,
        "basename": basename,
        "public_compact_candidate": public_compact_candidate,
        "private_raw_surface": bool(raw_marker or private_manifest),
        "first_blocker": first_blocker,
        "allowed_to_read": allowed_to_read,
        "recommended_action": recommended_action,
        "artifact_policy": {
            "adapter_kind": policy["adapter_kind"],
            "registry_backed": True,
            "public_filename_allowlist_count": len(policy["public_filenames"]),
            "raw_private_marker_count": len(policy["raw_private_markers"]),
        },
    }


def filter_public_benchmark_artifact_paths(
    paths: Iterable[str | Path],
    *,
    adapter_kind: str | None = None,
    extra_public_filenames: Iterable[Any] = (),
) -> dict[str, Any]:
    policy = _benchmark_artifact_policy(
        adapter_kind=adapter_kind,
        extra_public_filenames=extra_public_filenames,
    )
    classifications = [
        classify_benchmark_artifact_path(
            path,
            adapter_kind=policy["adapter_kind"],
            extra_public_filenames=extra_public_filenames,
        )
        for path in paths
    ]
    allowed = [item for item in classifications if item["allowed_to_read"]]
    blocked = [item for item in classifications if not item["allowed_to_read"]]
    blocked_reasons: dict[str, int] = {}
    for item in blocked:
        reason = str(item.get("first_blocker") or "unknown")
        blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
    return {
        "schema_version": "benchmark_artifact_path_filter_v0",
        "path_recorded": False,
        "allowed_to_read_count": len(allowed),
        "blocked_count": len(blocked),
        "allowed_artifact_basenames": [item["basename"] for item in allowed],
        "blocked_artifact_basenames": [item["basename"] for item in blocked],
        "blocked_reasons": blocked_reasons,
        "classifications": classifications,
        "artifact_policy": {
            "adapter_kind": policy["adapter_kind"],
            "registry_backed": True,
            "public_filename_allowlist_count": len(policy["public_filenames"]),
            "raw_private_marker_count": len(policy["raw_private_markers"]),
        },
        "public_boundary": {
            "full_paths_recorded": False,
            "raw_task_text_read": False,
            "trajectory_or_origin_log_read": False,
            "intended_use": "preflight benchmark artifact reads before compact ingest",
        },
    }


BENCHMARK_CANDIDATE_SOURCE_BOUNDARY_SCHEMA_VERSION = (
    "benchmark_candidate_source_boundary_v0"
)
BENCHMARK_CANDIDATE_SOURCE_PUBLIC_DOC_PREFIXES = (
    "docs/",
    "examples/",
    "goals/",
    "regression/",
)
BENCHMARK_CANDIDATE_SOURCE_ACTIVE_STATE_MARKERS = (
    "/active_goal_state.md",
    ".codex/goals/",
    ".local/goals/",
)
BENCHMARK_CANDIDATE_SOURCE_PRIVATE_RUN_MARKERS = (
    ".local/private-benchmark-jobs",
    "/private-benchmark-jobs/",
)
BENCHMARK_CANDIDATE_SOURCE_RAW_MARKERS = (
    "/agent/",
    "/origin_log",
    "/output/",
    "/outputs/",
    "/screenshots/",
    "/tasks/",
    "codex.txt",
    "trajectory.json",
    "instruction.md",
    "task.md",
    "lock.json",
    "config.json",
    "result.json",
)


def _candidate_source_public_doc_kind(normalized: str) -> str:
    lower = normalized.lower().lstrip("./")
    if lower.endswith(".md") and lower.startswith(BENCHMARK_CANDIDATE_SOURCE_PUBLIC_DOC_PREFIXES):
        return "public_doc"
    if lower.endswith(".py") and lower.startswith("examples/"):
        return "public_regression"
    return ""


def classify_benchmark_candidate_source_path(
    path: str | Path,
    *,
    adapter_kind: str | None = None,
    extra_public_filenames: Iterable[Any] = (),
) -> dict[str, Any]:
    """Classify a candidate-selection source without reading or echoing paths."""

    normalized = str(path).replace("\\", "/").rstrip("/")
    lower = normalized.lower()
    basename = normalized.rsplit("/", 1)[-1] if normalized else ""
    artifact = classify_benchmark_artifact_path(
        path,
        adapter_kind=adapter_kind,
        extra_public_filenames=extra_public_filenames,
    )
    public_doc_kind = _candidate_source_public_doc_kind(normalized)
    active_state_source = any(marker in lower for marker in BENCHMARK_CANDIDATE_SOURCE_ACTIVE_STATE_MARKERS)
    private_run_root = any(marker in lower for marker in BENCHMARK_CANDIDATE_SOURCE_PRIVATE_RUN_MARKERS)
    raw_marker = next(
        (marker for marker in BENCHMARK_CANDIDATE_SOURCE_RAW_MARKERS if marker in lower),
        "",
    )

    if artifact.get("allowed_to_read") is True:
        allowed = True
        first_blocker = ""
        source_kind = "compact_public_artifact"
        recommended_action = "use only reduced fields from the compact/public artifact"
    elif public_doc_kind:
        allowed = True
        first_blocker = ""
        source_kind = public_doc_kind
        recommended_action = "use public docs or regression fixtures for candidate routing"
    elif active_state_source and not raw_marker:
        allowed = True
        first_blocker = ""
        source_kind = "active_state_summary"
        recommended_action = "use active-state summaries; do not follow private artifact paths from them"
    elif private_run_root and not artifact.get("allowed_to_read"):
        allowed = False
        first_blocker = "private_runner_artifact_root_or_raw_child"
        source_kind = "blocked_private_runner_surface"
        recommended_action = "do not recurse private runner roots; pass explicit compact/public artifacts instead"
    elif raw_marker:
        allowed = False
        first_blocker = "raw_benchmark_artifact_surface"
        source_kind = "blocked_raw_artifact"
        recommended_action = "do not read raw transcripts, task bodies, trajectories, logs, configs, or result files for selection"
    else:
        allowed = False
        first_blocker = "unregistered_candidate_source"
        source_kind = "blocked_unregistered_source"
        recommended_action = "route candidate selection through docs, active state summaries, or compact/public JSON artifacts"

    return {
        "schema_version": "benchmark_candidate_source_classification_v0",
        "path_recorded": False,
        "basename": basename,
        "source_kind": source_kind,
        "allowed_for_candidate_selection": allowed,
        "first_blocker": first_blocker,
        "recommended_action": recommended_action,
        "artifact_allowed_to_read": bool(artifact.get("allowed_to_read")),
    }


def build_benchmark_candidate_source_boundary(
    paths: Iterable[str | Path],
    *,
    adapter_kind: str | None = None,
    extra_public_filenames: Iterable[Any] = (),
) -> dict[str, Any]:
    """Build a no-read boundary packet for benchmark candidate selection."""

    classifications = [
        classify_benchmark_candidate_source_path(
            path,
            adapter_kind=adapter_kind,
            extra_public_filenames=extra_public_filenames,
        )
        for path in paths
    ]
    allowed = [
        item for item in classifications if item["allowed_for_candidate_selection"]
    ]
    blocked = [
        item for item in classifications if not item["allowed_for_candidate_selection"]
    ]
    blocked_reasons: dict[str, int] = {}
    for item in blocked:
        reason = str(item.get("first_blocker") or "unknown")
        blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1

    return {
        "schema_version": BENCHMARK_CANDIDATE_SOURCE_BOUNDARY_SCHEMA_VERSION,
        "path_recorded": False,
        "allowed_source_count": len(allowed),
        "blocked_source_count": len(blocked),
        "clean": not blocked,
        "allowed_source_basenames": [item["basename"] for item in allowed],
        "blocked_source_basenames": [item["basename"] for item in blocked],
        "blocked_reasons": blocked_reasons,
        "classifications": classifications,
        "candidate_selection_policy": {
            "allowed_source_kinds": [
                "public_doc",
                "public_regression",
                "active_state_summary",
                "compact_public_artifact",
            ],
            "disallowed_source_kinds": [
                "private_runner_artifact_root_or_raw_child",
                "raw_benchmark_artifact_surface",
                "unregistered_candidate_source",
            ],
            "safe_private_artifact_glob": "*.public.json or *.compact.json only",
        },
        "read_boundary": {
            "files_opened": False,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "codex_transcript_read": False,
            "local_paths_recorded": False,
        },
        "next_action": (
            "run candidate selection using only allowed compact sources"
            if not blocked
            else "remove blocked raw/private sources before selecting or launching a benchmark candidate"
        ),
    }
