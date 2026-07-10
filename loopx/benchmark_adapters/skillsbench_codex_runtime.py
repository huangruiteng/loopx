from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loopx.codex_cli_goal_tui import resolve_codex_cli_binary


LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION = (
    "skillsbench_local_codex_participant_materialization_v0"
)
LOCAL_CODEX_PARTICIPANT_READY_MARKER = "LOOPX_LOCAL_CODEX_PARTICIPANT_READY"

_STRING_FIELDS = (
    "host_local_codex_cli_preflight_status",
    "host_local_codex_cli_preflight_first_blocker",
    "host_local_codex_cli_preflight_failure_category",
)
_BOOL_FIELDS = (
    "host_local_codex_cli_preflight_requested",
    "host_local_codex_cli_preflight_ready",
    "host_local_codex_cli_preflight_version_probe_invoked",
    "host_local_codex_cli_preflight_raw_output_recorded",
    "host_local_codex_cli_preflight_path_recorded",
)


def _size_bucket(size: int) -> str:
    if size <= 0:
        return "empty"
    if size < 200:
        return "1_199"
    if size < 1000:
        return "200_999"
    if size < 5000:
        return "1000_4999"
    return "5000_plus"


def materialize_local_codex_participant(
    *,
    codex_bin: str = "codex",
    timeout_sec: int = 120,
) -> dict[str, Any]:
    """Run a fixed CLI ping without retaining raw output, paths, or credentials."""

    resolved = resolve_codex_cli_binary(codex_bin)
    if not resolved:
        return {
            "schema_version": LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION,
            "ready": False,
            "first_blocker": "local_codex_cli_not_on_path",
            "codex_cli_available": False,
            "codex_cli_invoked": False,
            "raw_output_recorded": False,
            "raw_event_jsonl_recorded": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "a2a_worker_handshake_ready": False,
        }

    with tempfile.TemporaryDirectory(prefix="gh-skillsbench-codex-") as tmp:
        tmpdir = Path(tmp)
        output_path = tmpdir / "last-message.txt"
        prompt = (
            "Respond with exactly this single line and nothing else: "
            f"{LOCAL_CODEX_PARTICIPANT_READY_MARKER}"
        )
        cmd = [
            resolved,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "-C",
            str(tmpdir),
            "--output-last-message",
            str(output_path),
            "--json",
            prompt,
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=tmpdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else exc.stdout or b""
            stderr = exc.stderr if isinstance(exc.stderr, str) else exc.stderr or b""
            return {
                "schema_version": LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION,
                "ready": False,
                "first_blocker": "local_codex_cli_participant_timeout",
                "codex_cli_available": True,
                "codex_cli_invoked": True,
                "exit_code": None,
                "timeout_sec": timeout_sec,
                "stdout_len_bucket": _size_bucket(len(stdout)),
                "stderr_len_bucket": _size_bucket(len(stderr)),
                "raw_output_recorded": False,
                "raw_event_jsonl_recorded": False,
                "credential_values_recorded": False,
                "host_paths_recorded": False,
                "a2a_worker_handshake_ready": False,
            }

        try:
            marker = output_path.read_text(encoding="utf-8").strip()
        except OSError:
            marker = ""
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        ready = proc.returncode == 0 and marker == LOCAL_CODEX_PARTICIPANT_READY_MARKER
        first_blocker = (
            "local_codex_cli_participant_ready"
            if ready
            else "local_codex_cli_participant_exit_nonzero"
            if proc.returncode != 0
            else "local_codex_cli_participant_marker_missing"
        )
        return {
            "schema_version": LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION,
            "ready": ready,
            "first_blocker": first_blocker,
            "codex_cli_available": True,
            "codex_cli_invoked": True,
            "exit_code": proc.returncode,
            "marker_matched": marker == LOCAL_CODEX_PARTICIPANT_READY_MARKER,
            "json_event_count": sum(bool(line.strip()) for line in stdout.splitlines()),
            "stdout_len_bucket": _size_bucket(len(stdout)),
            "stderr_len_bucket": _size_bucket(len(stderr)),
            "raw_output_recorded": False,
            "raw_event_jsonl_recorded": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "a2a_worker_handshake_ready": False,
            "next_blocker_after_ready": (
                "skillsbench_local_acp_relay_missing" if ready else first_blocker
            ),
        }


def preflight_required(args: Any) -> bool:
    return bool(
        getattr(args, "host_local_acp_launch", False)
        and not getattr(args, "local_acp_relay_command", None)
        and not getattr(args, "reduce_only", False)
    )


def _fail(prerequisites: dict[str, Any], blocker: str, category: str) -> None:
    prerequisites["host_local_codex_cli_preflight_status"] = "failed"
    prerequisites["host_local_codex_cli_preflight_first_blocker"] = blocker
    prerequisites["host_local_codex_cli_preflight_failure_category"] = category


def run_preflight(args: Any, plan: dict[str, Any]) -> None:
    prerequisites = plan.setdefault("runner_prerequisites", {})
    prerequisites.update(
        {
            "host_local_codex_cli_preflight_requested": True,
            "host_local_codex_cli_preflight_ready": False,
            "host_local_codex_cli_preflight_status": "running",
            "host_local_codex_cli_preflight_first_blocker": "",
            "host_local_codex_cli_preflight_failure_category": "",
            "host_local_codex_cli_preflight_version_probe_invoked": False,
            "host_local_codex_cli_preflight_raw_output_recorded": False,
            "host_local_codex_cli_preflight_path_recorded": False,
        }
    )
    resolved = resolve_codex_cli_binary(args.local_codex_bin)
    if not resolved:
        _fail(
            prerequisites,
            "skillsbench_host_local_codex_cli_unavailable",
            "codex_cli_not_on_path",
        )
        raise RuntimeError("host-local Codex CLI unavailable")
    prerequisites["host_local_codex_cli_preflight_version_probe_invoked"] = True
    try:
        proc = subprocess.run(
            [resolved, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        proc = None
    if proc is None or proc.returncode != 0:
        _fail(
            prerequisites,
            "skillsbench_host_local_codex_cli_version_probe_failed",
            "codex_cli_version_probe_failed",
        )
        raise RuntimeError("host-local Codex CLI version probe failed")
    prerequisites["host_local_codex_cli_preflight_ready"] = True
    prerequisites["host_local_codex_cli_preflight_status"] = "ready"


def run_preflight_if_required(
    args: Any,
    plan: dict[str, Any],
    *,
    writeback: Callable[[], object],
) -> bool:
    if not preflight_required(args):
        return False
    try:
        run_preflight(args, plan)
    finally:
        writeback()
    return True


def compact_public_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact = {
        field: value[field][:180]
        for field in _STRING_FIELDS
        if isinstance(value.get(field), str) and value[field]
    }
    compact.update(
        {
            field: value[field]
            for field in _BOOL_FIELDS
            if isinstance(value.get(field), bool)
        }
    )
    return compact


def failure_attribution(
    value: dict[str, Any],
) -> tuple[str, str, list[str]] | None:
    if value.get("host_local_codex_cli_preflight_status") != "failed":
        return None
    category = str(value.get("host_local_codex_cli_preflight_failure_category") or "")
    label = "skillsbench_host_local_codex_cli_preflight_failed"
    if category:
        label = f"{label}_{category}"
    return label, label, [label, "skillsbench_runner_setup_error"]
