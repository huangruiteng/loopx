from __future__ import annotations

import re
from collections.abc import Mapping


_SETUP_ATTRIBUTION_FINGERPRINT_PATTERNS = {
    "skillsbench_docker_api_version_mismatch": "docker_api_version_mismatch",
    "skillsbench_docker_compose_plugin_unavailable": "docker_compose_plugin_unavailable",
    "skillsbench_docker_daemon_unavailable": "docker_daemon_unavailable",
    "skillsbench_docker_compose_port_conflict": "port_conflict",
    "skillsbench_docker_compose_pip_bootstrap_failure": "pip_bootstrap_failure",
    "skillsbench_docker_compose_apt_repository_failure": "apt_failure",
    "skillsbench_docker_compose_volume_mount_failure": "volume_mount_failure",
    "skillsbench_docker_compose_image_build_failure": "image_build",
}
_FINGERPRINT_SETUP_ATTRIBUTIONS = (
    ("docker_api_version_mismatch", "skillsbench_docker_api_version_mismatch"),
    (
        "docker_compose_plugin_unavailable",
        "skillsbench_docker_compose_plugin_unavailable",
    ),
    ("docker_daemon_unavailable", "skillsbench_docker_daemon_unavailable"),
    ("port_conflict", "skillsbench_docker_compose_port_conflict"),
    ("pip_bootstrap_failure", "skillsbench_docker_compose_pip_bootstrap_failure"),
    ("apt_failure", "skillsbench_docker_compose_apt_repository_failure"),
    ("volume_mount_failure", "skillsbench_docker_compose_volume_mount_failure"),
    ("image_build", "skillsbench_docker_compose_image_build_failure"),
)
_FAILURE_LINE_MARKERS = (
    "connection refused",
    "connection reset",
    "connection timed out",
    "could not connect",
    "did not complete successfully",
    "failed to download",
    "failed to fetch",
    "failed to solve",
    "gpg error",
    "hash sum mismatch",
    "manifest unknown",
    "max retries exceeded",
    "pull access denied",
    "read timed out",
    "temporary failure in name resolution",
)
_FAILURE_DEPENDENCY_CLASS_PATTERNS = (
    (
        "system_package",
        r"\bapt-get\b|\bapt\s+update\b|gpg error|hash sum mismatch|"
        r"failed to fetch",
    ),
    (
        "container_registry",
        r"registry-1\.docker\.io|docker\.io|gcr\.io|ghcr\.io|manifest unknown|"
        r"pull access denied|resolve source metadata",
    ),
    (
        "python_package",
        r"python\S*\s+-m\s+pip\s+install|pip3?\s+install|pypi\.|"
        r"pythonhosted\.org",
    ),
    ("python_uv", r"\buvx?\b|astral\.sh"),
    ("conda_package", r"\bconda\b|\bmamba\b|anaconda\.(?:com|org)"),
    ("node_package", r"\bnpm\b|\byarn\b|\bpnpm\b|registry\.npmjs\.org"),
    (
        "java_package",
        r"\bmvn\b|\bmaven\b|\bgradle\b|repo1\.maven\.org|"
        r"repo\.maven\.apache\.org",
    ),
    ("rust_package", r"\bcargo\b|\brustup\b|crates\.io|static\.rust-lang\.org"),
    ("go_module", r"\bgo\s+(?:mod|install|get)\b|proxy\.golang\.org"),
    ("git_source", r"\bgit\s+clone\b|github\.com|gitlab\.com"),
    ("http_download", r"\bcurl\b|\bwget\b"),
    (
        "cloud_object_storage",
        r"s3[.-][^/ ]*amazonaws\.com|storage\.googleapis\.com",
    ),
    ("model_artifact", r"huggingface\.co|hf\.co"),
)

_FAILURE_REASON_PATTERNS = (
    (
        "dns_resolution",
        r"temporary failure in name resolution|name or service not known|"
        r"temporary failure resolving|could not resolve host",
    ),
    (
        "connection_timeout",
        r"connection timed out|connect timeout|read timed out|operation timed out",
    ),
    ("connection_refused", r"connection refused|could not connect"),
    ("connection_reset", r"connection reset|remote end closed connection"),
    ("network_unreachable", r"network is unreachable|no route to host"),
    ("retry_exhausted", r"max retries exceeded"),
    (
        "proxy_connect",
        r"proxyerror|proxy error|tunnel connection failed|"
        r"cannot connect to proxy|could not connect to proxy",
    ),
    (
        "tls_or_certificate",
        r"certificate verif(?:y|ication) failed|ssl certificate problem|"
        r"tls handshake|could not handshake|"
        r"unable to get local issuer certificate",
    ),
    ("http_not_found", r"(?:http[^\n]*\s404\b|404 not found)"),
    ("http_server_error", r"(?:http[^\n]*\s5\d\d\b|5\d\d server error)"),
    ("apt_fetch_failed", r"failed to fetch"),
    ("apt_no_pubkey", r"\bno_pubkey\b"),
    (
        "apt_invalid_signature",
        r"invalid signature|at least one invalid signature was encountered",
    ),
    ("apt_unsigned_repository", r"repository(?:\s+\S+)?\s+is not signed"),
    ("apt_clearsigned_invalid", r"clearsigned file isn.t valid"),
    (
        "apt_signature_or_gpg",
        r"gpg error|no_pubkey|signatures? couldn.t be verified|"
        r"repository(?:\s+\S+)?\s+is not signed|clearsigned file isn.t valid",
    ),
    (
        "apt_hash_mismatch",
        r"hash sum mismatch|hashes of expected file|file has unexpected size",
    ),
    (
        "apt_release_expired",
        r"release file .* is not valid yet|release file .* expired|"
        r"does not have a release file",
    ),
    (
        "apt_package_unavailable",
        r"unable to locate package|has no installation candidate|"
        r"couldn.t find any package",
    ),
    (
        "pip_no_matching_distribution",
        r"no matching distribution found|"
        r"could not find a version that satisfies the requirement",
    ),
    (
        "pip_build_failure",
        r"failed building wheel|failed to build installable wheels|"
        r"pip subprocess to install build dependencies did not run successfully|"
        r"subprocess-exited-with-error",
    ),
    ("pip_os_error", r"could not install packages due to an oserror"),
    ("permission_denied", r"permission denied|operation not permitted"),
    ("missing_file", r"no such file|does not exist"),
    ("no_space_left", r"no space left on device"),
)

_FAILURE_DEPENDENCY_ENDPOINT_PATTERNS = (
    ("debian_repository", r"deb\.debian\.org|security\.debian\.org"),
    ("ubuntu_repository", r"archive\.ubuntu\.com|security\.ubuntu\.com"),
    ("ubuntu_repository_mirror", r"repo\.huaweicloud\.com/ubuntu"),
    ("apache_archive", r"archive\.apache\.org|dlcdn\.apache\.org"),
    ("maven_central", r"repo1\.maven\.org|repo\.maven\.apache\.org"),
    ("github_release", r"github\.com/.+/(?:releases|archive)/"),
    ("pypi_primary", r"pypi\.org|files\.pythonhosted\.org"),
    ("pypi_mirror", r"pypi\.tuna\.tsinghua\.edu\.cn"),
    ("docker_registry", r"registry-1\.docker\.io|docker\.io|gcr\.io|ghcr\.io"),
)

_TRANSIENT_FAILURE_REASONS = {
    "connection_refused",
    "connection_reset",
    "connection_timeout",
    "dns_resolution",
    "http_server_error",
    "network_unreachable",
    "proxy_connect",
    "retry_exhausted",
}
_DETERMINISTIC_FAILURE_REASONS = {
    "apt_package_unavailable",
    "http_not_found",
    "missing_file",
    "no_space_left",
    "permission_denied",
    "pip_build_failure",
    "pip_no_matching_distribution",
    "pip_os_error",
    "tls_or_certificate",
}

_APT_FAILURE_SUBTYPE_REASON_PRIORITY = (
    ("apt_no_pubkey", "missing_public_key"),
    ("apt_invalid_signature", "invalid_signature"),
    ("apt_unsigned_repository", "unsigned_repository"),
    ("apt_clearsigned_invalid", "clearsigned_invalid"),
    ("apt_signature_or_gpg", "signature_or_gpg"),
    ("apt_hash_mismatch", "hash_or_size_mismatch"),
    ("apt_release_expired", "release_metadata"),
    ("apt_package_unavailable", "package_unavailable"),
    ("dns_resolution", "dns_resolution"),
    ("proxy_connect", "proxy_connect"),
    ("tls_or_certificate", "tls_or_certificate"),
    ("http_not_found", "http_not_found"),
    ("http_server_error", "http_server_error"),
    ("network_unreachable", "network_unreachable"),
    ("connection_timeout", "connection_timeout"),
    ("connection_refused", "connection_refused"),
    ("connection_reset", "connection_reset"),
    ("retry_exhausted", "retry_exhausted"),
)


def _dependency_classes_for_lines(lines: list[str]) -> list[str]:
    return [
        label
        for label, pattern in _FAILURE_DEPENDENCY_CLASS_PATTERNS
        if any(re.search(pattern, line) for line in lines)
    ]


def _failure_reasons_for_lines(lines: list[str]) -> list[str]:
    return [
        label
        for label, pattern in _FAILURE_REASON_PATTERNS
        if any(re.search(pattern, line) for line in lines)
    ]


def _dependency_endpoints_for_lines(lines: list[str]) -> list[str]:
    return [
        label
        for label, pattern in _FAILURE_DEPENDENCY_ENDPOINT_PATTERNS
        if any(re.search(pattern, line) for line in lines)
    ]


def _apt_failure_subtype(
    *,
    dependency_classes: list[str],
    reasons: list[str],
) -> str:
    reason_set = set(reasons)
    apt_failure_present = (
        "system_package" in dependency_classes
        or "apt_fetch_failed" in reason_set
        or any(reason.startswith("apt_") for reason in reason_set)
    )
    if not apt_failure_present:
        return ""
    for reason, subtype in _APT_FAILURE_SUBTYPE_REASON_PRIORITY:
        if reason in reason_set:
            return subtype
    if "apt_fetch_failed" in reason_set:
        return "fetch_failed_unclassified"
    return "unclassified"


def _failure_signal_lines(error_text: str) -> list[str]:
    return [
        line.lower()
        for line in error_text.splitlines()
        if any(marker in line.lower() for marker in _FAILURE_LINE_MARKERS)
        or any(
            re.search(pattern, line.lower()) for _, pattern in _FAILURE_REASON_PATTERNS
        )
    ]


def skillsbench_failure_dependency_classes(error_text: str) -> list[str]:
    """Classify dependencies named on public-safe failure lines."""

    return _dependency_classes_for_lines(_failure_signal_lines(error_text))


def skillsbench_terminal_failure_signals(error_text: str) -> dict[str, object]:
    """Return the last dependency-bearing failure signal without raw text."""

    failure_lines = _failure_signal_lines(error_text)
    terminal_classes: list[str] = []
    terminal_reasons: list[str] = []
    terminal_endpoints: list[str] = []
    for line in reversed(failure_lines):
        if not terminal_classes:
            terminal_classes = _dependency_classes_for_lines([line])
        if not terminal_reasons:
            terminal_reasons = _failure_reasons_for_lines([line])
        if not terminal_endpoints:
            terminal_endpoints = _dependency_endpoints_for_lines([line])
        if terminal_classes and terminal_reasons and terminal_endpoints:
            break

    dependency_classes = _dependency_classes_for_lines(failure_lines)
    reasons = _failure_reasons_for_lines(failure_lines)
    endpoints = _dependency_endpoints_for_lines(failure_lines)
    reason_set = set(reasons)
    retry_reason_set = reason_set - {"apt_fetch_failed"}
    if not retry_reason_set:
        retry_reason_set = reason_set
    if retry_reason_set and retry_reason_set <= _TRANSIENT_FAILURE_REASONS:
        retryability = "retryable"
    elif retry_reason_set & _DETERMINISTIC_FAILURE_REASONS:
        retryability = (
            "mixed"
            if retry_reason_set & _TRANSIENT_FAILURE_REASONS
            else "non_retryable"
        )
    elif retry_reason_set:
        retryability = "unknown"
    else:
        retryability = "unknown"

    return {
        "failure_reason_codes": reasons,
        "apt_failure_subtype": _apt_failure_subtype(
            dependency_classes=dependency_classes,
            reasons=reasons,
        ),
        "terminal_failure_dependency_classes": terminal_classes,
        "terminal_failure_reason_codes": terminal_reasons,
        "failure_dependency_endpoints": endpoints,
        "terminal_failure_dependency_endpoints": terminal_endpoints,
        "retryability": retryability,
        "raw_error_recorded": False,
    }


def skillsbench_setup_failure_category(
    fingerprint: Mapping[str, object],
) -> str:
    """Map a public failure fingerprint to its most specific setup category."""

    matched_patterns = fingerprint.get("matched_patterns")
    if not isinstance(matched_patterns, list):
        return "skillsbench_docker_compose_setup_failure"
    matched = {str(item) for item in matched_patterns if isinstance(item, str)}
    return next(
        (
            attribution
            for pattern, attribution in _FINGERPRINT_SETUP_ATTRIBUTIONS
            if pattern in matched
        ),
        "skillsbench_docker_compose_setup_failure",
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
    matched = {str(item) for item in matched_patterns if isinstance(item, str)}
    if required_pattern in matched:
        return False

    replacement = skillsbench_setup_failure_category(fingerprint)
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
        pip_command.search(line) and any(marker in line for marker in command_failures)
        for line in text.splitlines()
    )


def skillsbench_error_len_bucket(text: str) -> str:
    size = len(text)
    if size <= 0:
        return "empty"
    if size < 200:
        return "1_199"
    if size < 500:
        return "200_499"
    if size < 1000:
        return "500_999"
    if size < 2000:
        return "1000_1999"
    return "2000_plus"


def skillsbench_runner_error_fingerprint(error_text: str) -> dict[str, object]:
    """Return a public-safe shape summary without copying raw error text."""

    text = error_text or ""
    lowered = text.lower()
    patterns = {
        "docker_compose_command_failed": r"docker compose command failed",
        "docker_api_version_mismatch": (
            r"client version \d+(?:\.\d+)+ is too new.*"
            r"maximum supported api version is \d+(?:\.\d+)+"
        ),
        "docker_compose_plugin_unavailable": (
            r"unknown flag:\s*--project-name[\s\S]*usage:\s+docker"
        ),
        "docker_daemon_unavailable": (
            r"cannot connect to the docker daemon|is the docker daemon running|"
            r"docker daemon is not running|colima is not running|error during connect"
        ),
        "service_unhealthy": r"unhealthy|healthcheck|health check",
        "container_exited": r"exited with code|container .* exited|exit code",
        "dependency_failed": r"dependency failed|depends_on|dependency",
        "network_failure": (
            r"network|connection refused|could not connect|read timed out|"
            r"connection timed out|connection reset|max retries exceeded"
        ),
        "volume_mount_failure": (
            r"invalid mount config|bind source path|mount denied|failed to mount|"
            r"error while mounting|volume [^\n]*(?:not found|does not exist|invalid)"
        ),
        "permission_denied": r"permission denied|operation not permitted",
        "missing_file": r"no such file|not found|does not exist",
        "codex_api_egress_failure": (
            r"codex api egress preflight|reverse tunnel proxy|"
            r"loopx_codex_api_reverse_tunnel_proxy"
        ),
        "task_output_quiet_timeout": r"codex_exec_task_output_quiet_timeout",
        "image_build": (
            r"failed to solve|failed to build|dockerfile|pull access denied|"
            r"manifest unknown"
        ),
        "port_conflict": (
            r"port is already allocated|address already in use|"
            r"ports are not available|bind for"
        ),
        "apt_failure": (
            r"apt-get|apt update|apt |gpg error|hash sum mismatch|failed to fetch"
        ),
        "pip_bootstrap_failure": r"$^",
        "subprocess_command_timeout": r"command timed out after \d+ seconds",
        "timeout": r"timeout|timed out|deadline",
    }
    matched = []
    for label, pattern in patterns.items():
        if label == "pip_bootstrap_failure":
            pattern_matched = skillsbench_pip_bootstrap_failure_evidence(lowered)
        else:
            pattern_matched = bool(re.search(pattern, lowered))
        if pattern_matched:
            matched.append(label)
    terminal_signals = skillsbench_terminal_failure_signals(text)
    return {
        "schema_version": "skillsbench_runner_failure_fingerprint_v0",
        "error_present": bool(text),
        "error_len_bucket": skillsbench_error_len_bucket(text),
        "line_count": len(text.splitlines()) if text else 0,
        "matched_patterns": matched,
        "failure_line_dependency_classes": skillsbench_failure_dependency_classes(text),
        **terminal_signals,
        "has_host_paths": bool(re.search(r"/Users/|/private/|/var/folders/", text)),
        "has_urls": bool(re.search(r"https?://", text)),
        "has_secret_like_tokens": bool(
            re.search(r"(?i)(api[_-]?key|token|password|secret)", text)
        ),
        "raw_error_recorded": False,
        "fingerprint_confidence": "coarse_public_safe_pattern_match",
    }
