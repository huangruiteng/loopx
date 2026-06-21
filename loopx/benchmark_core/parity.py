from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


CODEX_APP_PARITY_POSTHOC_CHECK_SCHEMA_VERSION = (
    "benchmark_codex_app_parity_posthoc_check_v0"
)
CODEX_APP_PARITY_TARGET = "codex_app_loopx_product_path"
CODEX_APP_PARITY_REQUIRED_CLI_CALLS = (
    "status",
    "quota_should_run",
    "todo_list",
    "history",
    "check",
)


def _safe_label(value: object, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9@._:/+= -]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _positive_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _contains_command(text: object, command: str) -> bool:
    normalized = _safe_label(text, limit=200).replace("-", "_")
    return command in normalized


def _loopx_cli_call_counts(interaction: Mapping[str, Any]) -> dict[str, int]:
    counts = {command: 0 for command in CODEX_APP_PARITY_REQUIRED_CLI_CALLS}

    raw_calls = interaction.get("loopx_cli_calls")
    if isinstance(raw_calls, Mapping):
        for command in CODEX_APP_PARITY_REQUIRED_CLI_CALLS:
            counts[command] = _positive_int(raw_calls.get(command))
    elif isinstance(raw_calls, list):
        for item in raw_calls:
            for command in CODEX_APP_PARITY_REQUIRED_CLI_CALLS:
                if _contains_command(item, command):
                    counts[command] += 1

    usage_counts = interaction.get("loopx_cli_state_usage_counts")
    if isinstance(usage_counts, Mapping):
        for command in CODEX_APP_PARITY_REQUIRED_CLI_CALLS:
            counts[command] = max(counts[command], _positive_int(usage_counts.get(command)))

    total = _positive_int(
        interaction.get("loopx_cli_call_count")
        or _as_mapping(raw_calls).get("total")
    )
    counts["total"] = max(total, sum(counts.values()))
    return counts


def _product_mode(benchmark_run: Mapping[str, Any], interaction: Mapping[str, Any]) -> bool:
    episode = _as_mapping(benchmark_run.get("episode_policy"))
    if interaction.get("product_mode") is True or episode.get("product_mode") is True:
        return True
    mode_text = " ".join(
        _safe_label(benchmark_run.get(key), limit=120)
        for key in ("mode", "route", "source_runner")
    ).lower()
    return "loopx_product" in mode_text or "codex_loopx" in mode_text


def _case_state_path(interaction: Mapping[str, Any]) -> str:
    value = str(interaction.get("case_goal_state_path") or "")
    if value.startswith("/app/.codex/goals/") and value.endswith(
        "/ACTIVE_GOAL_STATE.md"
    ):
        return value
    return ""


def build_codex_app_parity_posthoc_check(
    benchmark_run: Mapping[str, Any],
) -> dict[str, Any]:
    """Check whether a compact benchmark row has product-path evidence.

    The checker is intentionally post-hoc: it reads only public-safe
    `benchmark_run_v0` fields and compact interaction counters. It does not
    inspect raw task text, raw trajectories, verifier output, logs, credentials,
    or local private paths.
    """

    interaction = _as_mapping(benchmark_run.get("interaction_counters"))
    product_mode = _product_mode(benchmark_run, interaction)
    cli_counts = _loopx_cli_call_counts(interaction)
    missing_cli_calls = [
        command
        for command in CODEX_APP_PARITY_REQUIRED_CLI_CALLS
        if cli_counts.get(command, 0) <= 0
    ]

    case_path = _case_state_path(interaction)
    case_init_required = interaction.get("case_goal_state_init_required") is True
    case_initialized = (
        interaction.get("case_goal_state_initialized_before_agent") is True
        or _positive_int(interaction.get("loopx_case_state_writes")) > 0
    )
    trajectory_summary_present = (
        interaction.get("private_trajectory_summary_present") is True
        or interaction.get("controller_trace_present") is True
        or _positive_int(interaction.get("loopx_cli_call_count")) > 0
        or cli_counts["total"] > 0
    )

    safety_checks = {
        "raw_task_text_absent": interaction.get("raw_task_text_recorded") is not True
        and interaction.get("raw_task_prompt_recorded") is not True,
        "raw_reward_feedback_absent": interaction.get("reward_feedback_forwarded")
        is not True,
        "raw_verifier_output_absent": interaction.get("raw_verifier_output_recorded")
        is not True,
        "raw_agent_trajectory_absent": interaction.get("raw_agent_trajectory_recorded")
        is not True
        and interaction.get("raw_trace_recorded") is not True,
    }
    evidence_checks = {
        "canonical_case_active_state_path": bool(case_path),
        "case_active_state_initialized_before_agent": case_initialized,
        "loopx_cli_trace_present": cli_counts["total"] > 0,
        "required_loopx_cli_calls_present": not missing_cli_calls,
        "codex_cli_trajectory_summary_present": trajectory_summary_present,
    }

    missing_evidence = [
        key for key, value in evidence_checks.items() if product_mode and not value
    ]
    safety_failures = [key for key, value in safety_checks.items() if not value]
    full_product_claim_allowed = bool(
        product_mode and not missing_evidence and not safety_failures
    )

    if not product_mode:
        claim_level = "baseline_or_ablation_no_product_claim"
    elif full_product_claim_allowed:
        claim_level = "full_product_path_evidence_present"
    elif safety_failures:
        claim_level = "unsafe_or_leaky_artifact"
    else:
        claim_level = "product_mode_surrogate_missing_posthoc_evidence"

    return {
        "schema_version": CODEX_APP_PARITY_POSTHOC_CHECK_SCHEMA_VERSION,
        "parity_target": CODEX_APP_PARITY_TARGET,
        "benchmark_id": _safe_label(benchmark_run.get("benchmark_id"), limit=80),
        "mode": _safe_label(benchmark_run.get("mode"), limit=120),
        "route": _safe_label(benchmark_run.get("route"), limit=120),
        "product_mode": product_mode,
        "evidence_checks": evidence_checks,
        "safety_checks": safety_checks,
        "loopx_cli_call_counts": cli_counts,
        "missing_required_cli_calls": missing_cli_calls,
        "case_goal_state": {
            "init_required": case_init_required,
            "initialized_before_agent": case_initialized,
            "canonical_path_present": bool(case_path),
            "path_kind": "canonical_app_goal_state" if case_path else "missing_or_noncanonical",
        },
        "missing_evidence": missing_evidence,
        "safety_failures": safety_failures,
        "full_product_claim_allowed": full_product_claim_allowed,
        "claim_level": claim_level,
        "read_boundary": {
            "compact_benchmark_run_only": True,
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "raw_trajectory_read": False,
            "verifier_output_read": False,
            "credentials_read": False,
            "local_paths_recorded": False,
        },
    }


def render_codex_app_parity_posthoc_check_markdown(payload: Mapping[str, Any]) -> str:
    status = "allowed" if payload.get("full_product_claim_allowed") else "not_allowed"
    missing = payload.get("missing_evidence")
    missing_text = ", ".join(missing) if isinstance(missing, list) and missing else "none"
    safety = payload.get("safety_failures")
    safety_text = ", ".join(safety) if isinstance(safety, list) and safety else "none"
    return "\n".join(
        [
            "# Codex App Parity Posthoc Check",
            "",
            f"- claim_status: `{status}`",
            f"- claim_level: `{payload.get('claim_level', '')}`",
            f"- benchmark_id: `{payload.get('benchmark_id', '')}`",
            f"- mode: `{payload.get('mode', '')}`",
            f"- missing_evidence: `{missing_text}`",
            f"- safety_failures: `{safety_text}`",
            "- read_boundary: compact benchmark_run only; no raw logs, task text, trajectory, verifier output, credentials, or local private paths read.",
        ]
    )

