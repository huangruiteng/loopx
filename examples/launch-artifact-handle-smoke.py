"""Focused fake launch artifact smoke for GH-C22 (no real worker is launched).

Validates the ``terminal_bench_launch_artifact_handle_v0`` OBSERVE contract with
a fake handle + a temp run-root holding a fake pid file:
- the handle carries an ``allowed_poll_command`` + argv shape (a fresh/forgetful
  heartbeat can re-poll WITHOUT chat memory)
- a pid file pointing at our own pid    -> process_state == running
- a pid file pointing at a dead pid     -> process_state == ended
- a missing pid file                     -> process_state == unknown
- read_boundary gates process_state / artifact_refs off when declared
- the observation is compact-only        -> no raw bodies / logs / host paths
- handle building is public-safe         -> host paths reduce to basenames

Cross-platform: the underlying probe uses OpenProcess/GetExitCodeProcess on
Windows (so observing our own pid does NOT terminate this process) and
os.kill(pid, 0) on POSIX.

Run: python examples/launch-artifact-handle-smoke.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goal_harness.benchmark_adapters.terminal_bench import (  # noqa: E402
    TERMINAL_BENCH_LAUNCH_ARTIFACT_HANDLE_SCHEMA,
    build_terminal_bench_launch_artifact_handle,
    observe_terminal_bench_launch_artifact_handle,
)

COMPACT_OBSERVE_KEYS = {
    "schema_version",
    "run_basename",
    "job_name",
    "pid",
    "process_state",
    "first_blocker",
    "artifact_refs",
    "artifact_refs_present",
    "read_boundary",
}
errors = 0


def check(cond, msg):
    global errors
    if cond:
        print("  ok:", msg)
    else:
        errors += 1
        print("  FAIL:", msg)


def write_pid(run_root: Path, value: str) -> None:
    (run_root / "worker_materialization_probe.pid.private").write_text(
        value, encoding="utf-8"
    )


# 1) handle shape: public-safe + carries the memory-free poll command
handle = build_terminal_bench_launch_artifact_handle(
    run_basename="/abs/host/path/run-123",  # host path -> must reduce to basename
    job_name="C:\\Users\\someone\\jobs\\job-abc",
    artifact_ref_basenames=["runs/x/worker_materialization_probe_poll.public.json"],
)
check(
    handle["schema_version"] == TERMINAL_BENCH_LAUNCH_ARTIFACT_HANDLE_SCHEMA,
    "handle schema_version is v0",
)
check(handle["run_basename"] == "run-123", "run_basename reduced to public basename")
check(handle["job_name"] == "job-abc", "job_name reduced to public basename")
check(
    handle["allowed_poll_command"]
    == "goal-harness benchmark poll-worker-materialization-probe",
    "handle carries the allowed_poll_command (memory-free poll)",
)
check(
    "--job-name" in handle["poll_command_argv_shape"],
    "handle carries the poll_command_argv_shape",
)
check(
    handle["artifact_refs"] == ["worker_materialization_probe_poll.public.json"],
    "artifact refs reduced to compact basenames",
)
check(
    "/" not in handle["run_basename"] and "\\" not in handle["job_name"],
    "no host path separators leak into the handle",
)

# 2) observe: own pid -> running; artifact present detected
with tempfile.TemporaryDirectory(prefix="ghc22-smoke-") as tmp:
    run_root = Path(tmp)
    write_pid(run_root, str(os.getpid()))
    (run_root / "worker_materialization_probe_poll.public.json").write_text(
        "{}", encoding="utf-8"
    )
    obs = observe_terminal_bench_launch_artifact_handle(handle, run_root=run_root)
    check(obs["process_state"] == "running", f"own pid -> running (got {obs['process_state']})")
    check(obs.get("pid") == os.getpid(), "observed pid matches")
    check(
        "worker_materialization_probe_poll.public.json" in obs.get("artifact_refs_present", []),
        "present artifact ref detected",
    )
    check(
        set(obs).issubset(COMPACT_OBSERVE_KEYS),
        f"observe is compact-only (keys={sorted(obs)})",
    )

# 3) observe: dead pid -> ended
with tempfile.TemporaryDirectory(prefix="ghc22-smoke-") as tmp:
    run_root = Path(tmp)
    write_pid(run_root, "2000000000")
    obs = observe_terminal_bench_launch_artifact_handle(handle, run_root=run_root)
    check(obs["process_state"] == "ended", f"dead pid -> ended (got {obs['process_state']})")

# 4) observe: missing pid file -> unknown
with tempfile.TemporaryDirectory(prefix="ghc22-smoke-") as tmp:
    obs = observe_terminal_bench_launch_artifact_handle(handle, run_root=Path(tmp))
    check(obs["process_state"] == "unknown", "missing pid file -> unknown")
    check(obs.get("first_blocker") == "pid_file_missing", "missing pid file -> first_blocker")

# 5) read_boundary gating
with tempfile.TemporaryDirectory(prefix="ghc22-smoke-") as tmp:
    run_root = Path(tmp)
    write_pid(run_root, str(os.getpid()))
    (run_root / "worker_materialization_probe_poll.public.json").write_text("{}", encoding="utf-8")
    gated = build_terminal_bench_launch_artifact_handle(
        run_basename="run-123",
        artifact_ref_basenames=["worker_materialization_probe_poll.public.json"],
        read_boundary={
            "compact_only": True,
            "may_read_process_state": False,
            "may_read_artifact_refs": False,
        },
    )
    obs = observe_terminal_bench_launch_artifact_handle(gated, run_root=run_root)
    check(obs["process_state"] == "unknown", "process_state gated off -> unknown (not probed)")
    check("pid" not in obs, "pid not surfaced when process_state gated off")
    check("artifact_refs" not in obs, "artifact_refs withheld when gated off")

print(
    "\n===========Launch Artifact Handle Smoke: "
    + ("PASSED" if errors == 0 else f"{errors} FAILURES")
    + "==========="
)
sys.exit(0 if errors == 0 else 1)
