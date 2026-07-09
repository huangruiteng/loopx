from __future__ import annotations

import re


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
