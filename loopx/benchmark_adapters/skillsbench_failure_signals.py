from __future__ import annotations

import re


_SETUP_ATTRIBUTION_FINGERPRINT_PATTERNS = {
    "skillsbench_docker_daemon_unavailable": "docker_daemon_unavailable",
    "skillsbench_docker_compose_port_conflict": "port_conflict",
    "skillsbench_docker_compose_pip_bootstrap_failure": "pip_bootstrap_failure",
    "skillsbench_docker_compose_apt_repository_failure": "apt_failure",
    "skillsbench_docker_compose_volume_mount_failure": "volume_mount_failure",
    "skillsbench_docker_compose_image_build_failure": "image_build",
}
_FINGERPRINT_SETUP_ATTRIBUTIONS = (
    ("docker_daemon_unavailable", "skillsbench_docker_daemon_unavailable"),
    ("port_conflict", "skillsbench_docker_compose_port_conflict"),
    ("pip_bootstrap_failure", "skillsbench_docker_compose_pip_bootstrap_failure"),
    ("apt_failure", "skillsbench_docker_compose_apt_repository_failure"),
    ("volume_mount_failure", "skillsbench_docker_compose_volume_mount_failure"),
    ("image_build", "skillsbench_docker_compose_image_build_failure"),
)


def reconcile_skillsbench_setup_attribution(
    benchmark_run: dict[str, object],
) -> bool:
    """Keep setup attribution consistent with its public fingerprint."""

    current = str(benchmark_run.get("score_failure_attribution") or "")
    required_pattern = _SETUP_ATTRIBUTION_FINGERPRINT_PATTERNS.get(current)
    fingerprint = benchmark_run.get("runner_failure_fingerprint")
    if not required_pattern or not isinstance(fingerprint, dict):
        return False
    matched_patterns = fingerprint.get("matched_patterns")
    if not isinstance(matched_patterns, list):
        return False
    matched = {
        str(item)
        for item in matched_patterns
        if isinstance(item, str)
    }
    if required_pattern in matched:
        return False

    replacement = next(
        (
            attribution
            for pattern, attribution in _FINGERPRINT_SETUP_ATTRIBUTIONS
            if pattern in matched
        ),
        "skillsbench_docker_compose_setup_failure",
    )
    benchmark_run["score_failure_attribution"] = replacement
    for field in ("first_blocker", "repeat_blocked_by"):
        if benchmark_run.get(field) == current:
            benchmark_run[field] = replacement

    specific_labels = set(_SETUP_ATTRIBUTION_FINGERPRINT_PATTERNS)
    raw_labels = benchmark_run.get("failure_attribution_labels")
    if not isinstance(raw_labels, list):
        raw_labels = []
    labels = [replacement] + [
        item
        for item in raw_labels
        if isinstance(item, str)
        and item not in specific_labels
        and item != "skillsbench_docker_compose_unclassified_setup_failure"
    ]
    for item in (
        "skillsbench_docker_compose_setup_failure",
        "skillsbench_environment_setup_error",
        "skillsbench_setup_attribution_reconciled_from_fingerprint",
    ):
        if item not in labels:
            labels.append(item)
    if (
        replacement == "skillsbench_docker_compose_setup_failure"
        and "skillsbench_docker_compose_unclassified_setup_failure" not in labels
    ):
        labels.append("skillsbench_docker_compose_unclassified_setup_failure")
    benchmark_run["failure_attribution_labels"] = labels

    runner_failure = benchmark_run.get("runner_failure")
    if isinstance(runner_failure, dict):
        for field in ("exception_type", "failure_class"):
            if runner_failure.get(field) == current:
                runner_failure[field] = replacement
    attempt_accounting = benchmark_run.get("attempt_accounting")
    if (
        isinstance(attempt_accounting, dict)
        and attempt_accounting.get("failure_label") == current
    ):
        attempt_accounting["failure_label"] = replacement
    diagnostic = benchmark_run.get("compose_setup_diagnostic")
    if isinstance(diagnostic, dict):
        if diagnostic.get("failure_class") == current:
            diagnostic["failure_class"] = replacement
        diagnostic["attribution_reconciled_from_fingerprint"] = True
    trials = benchmark_run.get("trials")
    if isinstance(trials, list):
        for trial in trials:
            if isinstance(trial, dict) and trial.get("exception_type") == current:
                trial["exception_type"] = replacement
    return True


def skillsbench_pip_bootstrap_failure_evidence(error_text: str) -> bool:
    text = error_text.lower()
    explicit_markers = (
        "no matching distribution found",
        "could not find a version that satisfies the requirement",
        "failed building wheel",
        "failed to build installable wheels",
        "subprocess-exited-with-error",
        "could not install packages due to an oserror",
        "pip._vendor.",
        "pip subprocess to install build dependencies did not run successfully",
    )
    if any(marker in text for marker in explicit_markers):
        return True

    package_hosts = (
        "files.pythonhosted.org",
        "pypi.org",
        "pypi.tuna.tsinghua.edu.cn",
    )
    network_failures = (
        "read timed out",
        "connection timed out",
        "connection reset",
        "temporary failure in name resolution",
        "max retries exceeded",
    )
    if any(
        any(host in line for host in package_hosts)
        and any(marker in line for marker in network_failures)
        for line in text.splitlines()
    ):
        return True

    pip_command = re.compile(
        r"(?:python3?|python)\s+-m\s+pip\s+install\b|pip3?\s+install\b"
    )
    command_failures = (
        "did not complete successfully",
        "returned a non-zero code",
        "exit code:",
        " error:",
        " failed",
    )
    return any(
        pip_command.search(line)
        and any(marker in line for marker in command_failures)
        for line in text.splitlines()
    )
