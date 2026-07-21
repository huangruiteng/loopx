"""Public-safe SkillsBench verifier bootstrap attribution helpers."""

from __future__ import annotations

import os
import re
import shlex
import stat
from pathlib import Path
from typing import Any

from loopx.benchmark_adapters import skillsbench_proxy_runtime as proxy_runtime


VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN = (
    "# BEGIN LOOPX_SKILLSBENCH_VERIFIER_UV_BOOTSTRAP_MIRROR"
)
VERIFIER_UV_BOOTSTRAP_MIRROR_END = (
    "# END LOOPX_SKILLSBENCH_VERIFIER_UV_BOOTSTRAP_MIRROR"
)
DEFAULT_VERIFIER_UV_RELEASE_MIRROR_BASE = (
    "https://releases.astral.sh/github/uv/releases/download"
)
DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST = "releases.astral.sh"
DEFAULT_DOCKER_PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"


def _strip_marker_block(text: str, begin: str, end: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == begin:
            skipping = True
            continue
        if line.strip() == end:
            skipping = False
            continue
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + "\n"


def _write_text_atomic(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary = path.with_name(f".{path.name}.loopx-bootstrap.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def skillsbench_verifier_bootstrap_risk(task_path: Path) -> dict[str, Any]:
    """Return public-safe verifier dependency bootstrap risk flags."""

    verifier = proxy_runtime.skillsbench_verifier_script(task_path)
    result: dict[str, Any] = {
        "verifier_present": verifier.exists(),
        "verifier_bootstrap_risk_detected": False,
        "verifier_uv_bootstrap_risk_detected": False,
        "verifier_external_download_risk_detected": False,
        "verifier_package_install_risk_detected": False,
        "verifier_bootstrap_risk_categories": [],
    }
    if not verifier.exists():
        return result
    try:
        text = verifier.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result

    uv_versions = verifier_uv_bootstrap_versions(text)
    if uv_versions:
        result["verifier_uv_bootstrap_version"] = uv_versions[0]
    categories: list[str] = []
    if re.search(
        r"astral\.sh/uv|(?:^|[;&|(\s])uv(?:x|\s+add|\s+sync|\s+pip|\s+tool)",
        text,
    ):
        result["verifier_uv_bootstrap_risk_detected"] = True
        categories.append("uv_bootstrap")
    if re.search(r"(?:curl|wget)\s+[^;\n]*(?:https?://|astral\.sh)", text):
        result["verifier_external_download_risk_detected"] = True
        categories.append("external_download")
    if re.search(
        r"(?:python\s+-m\s+pip|pip3?|uv\s+pip|uv\s+add|"
        r"poetry\s+install|npm\s+install|pnpm\s+install|"
        r"yarn\s+install|apt-get\s+(?:update|install))",
        text,
    ):
        result["verifier_package_install_risk_detected"] = True
        categories.append("package_install")
    result["verifier_bootstrap_risk_categories"] = sorted(set(categories))
    result["verifier_bootstrap_risk_detected"] = bool(categories)
    return result


def verifier_uv_bootstrap_versions(text: str) -> list[str]:
    versions: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"https?://astral\.sh/uv/(?P<version>[0-9A-Za-z][0-9A-Za-z._+-]*)/install\.sh",
        text,
    ):
        version = match.group("version")
        if version and version not in seen:
            versions.append(version)
            seen.add(version)
    return versions


def patch_verifier_uv_bootstrap_mirror(verifier: Path) -> dict[str, Any]:
    """Route staged verifier uv bootstrap through package and release mirrors."""

    metadata: dict[str, Any] = {
        "verifier_uv_bootstrap_risk_detected": False,
        "verifier_uv_bootstrap_mirror_patch_required": False,
        "verifier_uv_bootstrap_mirror_patch_applied": False,
        "verifier_uv_bootstrap_pip_fallback_patch_applied": False,
        "verifier_uv_env_source_guard_patch_applied": False,
    }
    if not verifier.exists():
        return metadata
    try:
        original = verifier.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return metadata
    text = _strip_marker_block(
        original,
        VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN,
        VERIFIER_UV_BOOTSTRAP_MIRROR_END,
    )
    versions = verifier_uv_bootstrap_versions(text)
    if not versions:
        return metadata

    version = versions[0]
    block = (
        f"{VERIFIER_UV_BOOTSTRAP_MIRROR_BEGIN}\n"
        "# Prefer the PyPI uv wheel for verifier bootstrap; the official uv\n"
        "# installer release tarball remains as a bounded fallback.\n"
        f"loopx_uv_release_mirror={shlex.quote(DEFAULT_VERIFIER_UV_RELEASE_MIRROR_BASE)}\n"
        f"loopx_uv_version={shlex.quote(version)}\n"
        "if ! command -v uvx >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then\n"
        "  loopx_pip_break_system_packages=''\n"
        "  if python3 -m pip install --help 2>/dev/null | grep -q -- '--break-system-packages'; then\n"
        "    loopx_pip_break_system_packages='--break-system-packages'\n"
        "  fi\n"
        "  python3 -m pip install ${loopx_pip_break_system_packages} \\\n"
        "    --timeout 120 --retries 5 \\\n"
        f"    --index-url {shlex.quote(DEFAULT_DOCKER_PIP_INDEX_URL)} \\\n"
        "    \"uv==${loopx_uv_version}\" || true\n"
        "  unset loopx_pip_break_system_packages\n"
        "fi\n"
        "if [ -z \"${INSTALLER_DOWNLOAD_URL:-}\" ]; then\n"
        "  export INSTALLER_DOWNLOAD_URL=\"${loopx_uv_release_mirror}/${loopx_uv_version}\"\n"
        "fi\n"
        "loopx_uv_installer_timeout_sec=${LOOPX_SKILLSBENCH_UV_INSTALL_TIMEOUT_SEC:-180}\n"
        f"{VERIFIER_UV_BOOTSTRAP_MIRROR_END}"
    )
    patched_lines: list[str] = []
    inserted = False
    for line in text.splitlines():
        if not inserted and "astral.sh/uv/" in line and "install.sh" in line:
            patched_lines.extend(block.splitlines())
            inserted = True
            if "curl" in line and "|" in line:
                fallback_line = shlex.quote(line)
                patched_lines.extend(
                    [
                        "if ! command -v uvx >/dev/null 2>&1; then",
                        "  if command -v timeout >/dev/null 2>&1; then",
                        f"    timeout \"${{loopx_uv_installer_timeout_sec}}\" sh -c {fallback_line}",
                        "  else",
                        f"    sh -c {fallback_line}",
                        "  fi",
                        "fi",
                    ]
                )
                continue
        patched_lines.append(line)
    if not inserted:
        patched_lines.extend(block.splitlines())
    patched = "\n".join(patched_lines).rstrip() + "\n"
    patched, source_guard_applied = _patch_verifier_uv_env_source_guard(patched)
    if patched != original:
        _write_text_atomic(verifier, patched)
    metadata.update(
        {
            "verifier_uv_bootstrap_risk_detected": True,
            "verifier_uv_bootstrap_mirror_patch_required": True,
            "verifier_uv_bootstrap_mirror_patch_applied": True,
            "verifier_uv_bootstrap_pip_fallback_patch_applied": True,
            "verifier_uv_env_source_guard_patch_applied": source_guard_applied,
            "verifier_uv_bootstrap_version": version,
            "verifier_uv_bootstrap_mirror_host": DEFAULT_VERIFIER_UV_RELEASE_MIRROR_HOST,
        }
    )
    return metadata


def _patch_verifier_uv_env_source_guard(text: str) -> tuple[str, bool]:
    source_lines = {
        'source "$HOME/.local/bin/env"',
        "source $HOME/.local/bin/env",
        '. "$HOME/.local/bin/env"',
        ". $HOME/.local/bin/env",
    }
    replacement = [
        'if [ -f "$HOME/.local/bin/env" ]; then',
        '  . "$HOME/.local/bin/env"',
        "fi",
    ]
    patched_lines: list[str] = []
    applied = False
    for line in text.splitlines():
        if line.strip() in source_lines:
            indent = line[: len(line) - len(line.lstrip())]
            patched_lines.extend(f"{indent}{part}" for part in replacement)
            applied = True
        else:
            patched_lines.append(line)
    if not applied:
        return text, False
    return "\n".join(patched_lines).rstrip() + "\n", True


GENERIC_MISSING_ATTRIBUTIONS = {
    "",
    "none",
    "official_score_missing",
    "skillsbench_result_json_missing_after_runner_exit",
    "skillsbench_runner_error",
    "skillsbench_runner_failed_before_agent_install",
    "skillsbench_runner_interrupted_before_official_result",
    "skillsbench_runner_setup_error",
    "skillsbench_verifier_reward_missing",
}

SETUP_PREFLIGHT_REPLACEABLE_ATTRIBUTIONS = GENERIC_MISSING_ATTRIBUTIONS | {
    "skillsbench_product_mode_lifecycle_missing",
    "skillsbench_remote_bridge_agent_operation_trace_missing",
}

GENERIC_MISSING_LABELS = {
    "official_score_missing",
    "skillsbench_result_json_missing_after_runner_exit",
    "skillsbench_runner_error",
    "skillsbench_runner_failed_before_agent_install",
    "skillsbench_runner_interrupted_before_official_result",
    "skillsbench_runner_setup_error",
    "skillsbench_verifier_reward_missing",
}

SETUP_PREFLIGHT_REPLACEABLE_LABELS = GENERIC_MISSING_LABELS | {
    "skillsbench_product_mode_lifecycle_missing",
    "skillsbench_product_mode_uncountable_treatment",
    "skillsbench_remote_bridge_agent_operation_trace_missing",
}


def _public_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def apply_skillsbench_verifier_bootstrap_missing_score_attribution(
    compact: dict[str, Any],
    *,
    task_staging: dict[str, Any] | None = None,
    setup_preflight: dict[str, Any] | None = None,
) -> bool:
    """Classify missing official score when public preflight saw bootstrap risk."""

    if compact.get("official_score_status") != "missing":
        return False
    if compact.get("official_score") is not None:
        return False

    task_staging = task_staging if isinstance(task_staging, dict) else {}
    setup_preflight = setup_preflight if isinstance(setup_preflight, dict) else {}
    current_attribution = str(compact.get("score_failure_attribution") or "")
    existing_labels = [
        label
        for label in compact.get("failure_attribution_labels", [])
        if isinstance(label, str) and label
    ]
    explicit_final_timeout = (
        current_attribution == "skillsbench_final_verifier_timeout"
        or "skillsbench_final_verifier_timeout" in existing_labels
    )
    task_score = (
        compact.get("official_task_score")
        if isinstance(compact.get("official_task_score"), dict)
        else {}
    )
    score_kind = str(task_score.get("kind") or "")
    if score_kind and "missing" not in score_kind and not explicit_final_timeout:
        return False

    uv_bootstrap_risk = (
        task_staging.get("verifier_uv_bootstrap_risk_detected") is True
        or setup_preflight.get("verifier_uv_bootstrap_risk_detected") is True
    )
    package_install_risk = (
        task_staging.get("verifier_package_install_risk_detected") is True
        or setup_preflight.get("verifier_package_install_risk_detected") is True
    )
    verifier_bootstrap_risk = (
        task_staging.get("verifier_bootstrap_risk_detected") is True
        or setup_preflight.get("verifier_bootstrap_risk_detected") is True
    )
    bootstrap_light_blocking_fields = setup_preflight.get(
        "bootstrap_light_blocking_fields"
    )
    if not isinstance(bootstrap_light_blocking_fields, list):
        bootstrap_light_blocking_fields = []
    explicit_bootstrap_blocked = (
        task_staging.get("verifier_bootstrap_risk_preflight_blocked") is True
        or setup_preflight.get("first_blocker") == "verifier_bootstrap_risk"
    )
    pre_agent_setup_blocked = (
        explicit_bootstrap_blocked
        or task_staging.get("staged") is False
        or setup_preflight.get("bootstrap_light_candidate_eligible") is False
        or "verifier_package_install_risk_detected" in bootstrap_light_blocking_fields
        or "verifier_bootstrap_risk_detected" in bootstrap_light_blocking_fields
    )
    verifier_bootstrap_blocked = explicit_bootstrap_blocked or (
        verifier_bootstrap_risk
        and pre_agent_setup_blocked
        and setup_preflight.get("status") == "verifier_bootstrap_risk_detected"
    )
    if not (
        uv_bootstrap_risk
        or verifier_bootstrap_blocked
        or (package_install_risk and verifier_bootstrap_risk)
    ):
        return False

    replaceable_attributions = (
        SETUP_PREFLIGHT_REPLACEABLE_ATTRIBUTIONS
        if pre_agent_setup_blocked
        else GENERIC_MISSING_ATTRIBUTIONS
    )
    if explicit_final_timeout:
        replaceable_attributions = replaceable_attributions | {
            "skillsbench_final_verifier_timeout"
        }
    if current_attribution not in replaceable_attributions:
        return False

    replaceable_labels = (
        SETUP_PREFLIGHT_REPLACEABLE_LABELS
        if pre_agent_setup_blocked
        else GENERIC_MISSING_LABELS
    )
    if explicit_final_timeout:
        replaceable_labels = replaceable_labels | {
            "skillsbench_final_verifier_timeout",
            "skillsbench_verifier_timeout",
        }
    if any(label not in replaceable_labels for label in existing_labels):
        return False

    attribution = (
        "verifier_dependency_bootstrap_timeout"
        if explicit_final_timeout
        else "verifier_dependency_install_failure"
    )
    compact["score_failure_attribution"] = attribution
    compact["first_blocker"] = attribution
    compact["repeat_blocked_by"] = attribution
    compact["official_score_comparable_to_native_codex"] = False
    compact["official_score_comparable_to_loopx_treatment"] = False
    compact["verifier_failure_attribution_count"] = max(
        1,
        _public_int(compact.get("verifier_failure_attribution_count")),
    )
    compact["verifier_dependency_failure_count"] = max(
        1,
        _public_int(compact.get("verifier_dependency_failure_count")),
    )

    labels = [label for label in existing_labels if label not in replaceable_labels]
    for label in (
        attribution,
        "skillsbench_verifier_bootstrap_missing_official_score",
    ):
        if label not in labels:
            labels.append(label)
    if uv_bootstrap_risk:
        label = "verifier_uv_install_or_download_failure"
        if label not in labels:
            labels.append(label)
    if package_install_risk:
        label = "skillsbench_verifier_package_install_risk"
        if label not in labels:
            labels.append(label)
    if verifier_bootstrap_blocked:
        label = "skillsbench_verifier_bootstrap_preflight_blocked"
        if label not in labels:
            labels.append(label)
    compact["failure_attribution_labels"] = labels

    if isinstance(task_score, dict):
        task_score = dict(task_score)
        task_score["kind"] = (
            "skillsbench_verifier_bootstrap_timeout_reward_missing"
            if explicit_final_timeout
            else "skillsbench_verifier_bootstrap_reward_missing"
        )
        task_score["value"] = None
        task_score["passed"] = False
        compact["official_task_score"] = task_score

    runner_failure = compact.get("runner_failure")
    if isinstance(runner_failure, dict):
        runner_failure["failure_class"] = attribution
        runner_failure["verifier_bootstrap_missing_score_attributed"] = True

    attempt_accounting = compact.get("attempt_accounting")
    if isinstance(attempt_accounting, dict) and (
        pre_agent_setup_blocked or explicit_final_timeout
    ):
        attempt_accounting["failure_label"] = attribution
        attempt_accounting["failure_class"] = (
            "verifier_bootstrap_failed"
            if explicit_final_timeout
            else "job_materialization_failed"
        )

    diagnostic: dict[str, Any] = {
        "schema_version": "skillsbench_verifier_bootstrap_missing_score_diagnostic_v0",
        "status": (
            "verifier_dependency_bootstrap_timed_out"
            if explicit_final_timeout
            else "missing_official_score_with_verifier_bootstrap_risk"
        ),
        "score_failure_attribution": attribution,
        "verifier_uv_bootstrap_risk_detected": uv_bootstrap_risk,
        "verifier_package_install_risk_detected": package_install_risk,
        "verifier_bootstrap_risk_preflight_blocked": verifier_bootstrap_blocked,
        "pre_agent_setup_blocked": pre_agent_setup_blocked,
        "verifier_uv_bootstrap_mirror_patch_required": task_staging.get(
            "verifier_uv_bootstrap_mirror_patch_required"
        )
        is True,
        "verifier_uv_bootstrap_mirror_patch_applied": task_staging.get(
            "verifier_uv_bootstrap_mirror_patch_applied"
        )
        is True,
        "verifier_uv_bootstrap_pip_fallback_patch_applied": task_staging.get(
            "verifier_uv_bootstrap_pip_fallback_patch_applied"
        )
        is True,
        "raw_verifier_output_read": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
        "verifier_dependency_cache_required": task_staging.get(
            "verifier_dependency_cache_required"
        )
        is True,
        "verifier_dependency_cache_env_patch_applied": task_staging.get(
            "verifier_dependency_cache_env_patch_applied"
        )
        is True,
        "next_diagnostic_action": (
            "warm_verifier_dependency_cache_then_rerun"
            if explicit_final_timeout
            else "prewarm_or_fail_fast_verifier_bootstrap_before_rerun"
        ),
    }
    for field in (
        "verifier_uv_bootstrap_version",
        "verifier_uv_bootstrap_mirror_host",
    ):
        value = task_staging.get(field) or setup_preflight.get(field)
        if isinstance(value, str) and value:
            diagnostic[field] = value[:180]
    compact["verifier_bootstrap_diagnostic"] = diagnostic

    validation = (
        compact.get("validation")
        if isinstance(compact.get("validation"), dict)
        else {}
    )
    validation["raw_verifier_output_read"] = False
    validation["verifier_bootstrap_missing_score_classified"] = True
    compact["validation"] = validation
    return True
