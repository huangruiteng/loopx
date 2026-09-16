#!/usr/bin/env python3
"""Regression fixture for #3092: fresh-project onboarding defects.

Covers:
  - Defect 1: guided todo template must use ``--claimed-by`` (not ``--agent-id``)
              so the emitted command is accepted by ``loopx todo add``.
  - Defect 2: ``agent-onboard`` on a project with no ``.loopx/registry.json``
              must return a typed gate, not raise ``FileNotFoundError``.
  - Guided takeover: when the goal already has a runnable Todo frontier,
                     authoring is projected as a typed Todo delta instead of an
                     unconditional ``write_ordered_todos`` step. `connect` no
                     longer seeds that frontier, so the fixture writes the first
                     agent Todo the way a real caller now does.

See: https://github.com/huangruiteng/loopx/issues/3092
Fix: https://github.com/huangruiteng/loopx/pull/3093
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.bootstrap_command_pack import build_start_goal_guided_packet  # noqa: E402

PASS = 0
FAIL = 0


def run_cli(
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a ``loopx`` CLI command via subprocess, returning JSON output."""
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
        timeout=300,
    )


def check(label: str, condition: bool) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {label}")
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


def _register_agent_in_registry(registry_path: Path, goal_id: str, agent_id: str) -> None:
    """Add an agent to the project-local registry coordination block.

    This mirrors the pattern used by existing smokes (e.g.
    agent-onboard-host-loop-activation-smoke.py) which write the registry
    fixture directly rather than going through ``register-agent`` (which
    requires a global registry route).
    """
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for goal in registry.get("goals", []):
        if goal.get("id") == goal_id:
            coordination = goal.setdefault("coordination", {})
            agents = coordination.setdefault("registered_agents", [])
            if agent_id not in agents:
                agents.append(agent_id)
            break
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _require_guided_todo_delta_template(
    guided_packet: dict[str, object],
    *,
    label: str,
) -> str:
    """Require the typed authoring path used by fresh bootstrap fixtures."""
    transaction = guided_packet.get("guided_transaction", {})
    ordered_steps = (
        transaction.get("ordered_steps", [])
        if isinstance(transaction, dict)
        else []
    )
    steps = [step for step in ordered_steps if isinstance(step, dict)]
    legacy_steps = [
        step for step in steps if step.get("id") == "write_ordered_todos"
    ]
    delta_steps = [step for step in steps if step.get("id") == "apply_todo_delta"]

    check(f"{label}: legacy Todo authoring is absent", not legacy_steps)
    check(f"{label}: contains exactly one Todo delta", len(delta_steps) == 1)
    if len(delta_steps) != 1:
        return ""

    delta_step = delta_steps[0]
    todo_delta = delta_step.get("todo_delta", {})
    check(
        f"{label}: Todo delta uses the guided takeover schema",
        isinstance(todo_delta, dict)
        and todo_delta.get("schema_version") == "loopx_guided_todo_delta_v0",
    )
    check(
        f"{label}: Todo delta exposes a runnable frontier",
        isinstance(todo_delta, dict)
        and todo_delta.get("runnable_frontier_count", 0) >= 1
        and bool(todo_delta.get("frontier")),
    )
    template = delta_step.get("add_new_command_template", "")
    check(
        f"{label}: Todo delta exposes an add-new template",
        isinstance(template, str) and bool(template),
    )
    return template if isinstance(template, str) else ""


# ---------------------------------------------------------------------------
# Scenario 1: agent-onboard on a bare project with no .loopx/ directory
# (Defect 2 regression: must return a typed gate, not FileNotFoundError)
# ---------------------------------------------------------------------------
def test_unconnected_agent_onboard(project: Path) -> None:
    print("\n=== Scenario 1: agent-onboard on unconnected project ===")

    result = run_cli(
        "agent-onboard",
        "--agent-type", "claude-code",
        "--project", str(project),
        check=False,
    )
    # The command must not crash with a traceback.
    check(
        "agent-onboard exits without traceback",
        "FileNotFoundError" not in (result.stderr + result.stdout),
    )

    # It should produce parseable JSON.
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    check("agent-onboard returns valid JSON", bool(payload))

    # The JSON should be a typed gate or structured packet, not a crash.
    # Before the fix (#3093): FileNotFoundError traceback.
    # After the fix: an identity_selection_gate packet with
    # activation_allowed: false (the project needs bootstrap/registration).
    identity_gate = payload.get("identity_selection_gate")
    check(
        "response is a typed gate or structured packet (not a crash)",
        payload.get("gate") == "project_not_connected"
        or payload.get("ok") is False
        or payload.get("connection_state") == "not_connected"
        or (
            isinstance(identity_gate, dict)
            and identity_gate.get("activation_allowed") is False
        ),
    )


# ---------------------------------------------------------------------------
# Scenario 2 & 3: guided todo template uses --claimed-by and is accepted
# (Defect 1 regression)
# ---------------------------------------------------------------------------
def test_guided_template_acceptance(project: Path, goal_id: str) -> None:
    print("\n=== Scenario 2: bootstrap + guided template validation ===")

    # Step 1: Bootstrap the project (local-only, no global sync).
    bootstrap = run_cli(
        "bootstrap",
        "--project", str(project),
        "--goal-id", goal_id,
        "--objective", "regression test for #3092",
        "--adapter-kind", "read_only_project_map_v0",
        "--adapter-status", "connected-read-only",
        "--no-global-sync",
        check=False,
    )
    check("bootstrap exits 0", bootstrap.returncode == 0)

    # Step 2: Register an agent by writing directly to the project registry.
    agent_id = "smoke-agent-1"
    registry_path = project / ".loopx" / "registry.json"
    check("registry.json exists after bootstrap", registry_path.exists())
    if registry_path.exists():
        _register_agent_in_registry(registry_path, goal_id, agent_id)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        goal_entry = next(
            (g for g in registry.get("goals", []) if g.get("id") == goal_id),
            {},
        )
        registered_agents = (
            goal_entry.get("coordination", {}).get("registered_agents", [])
        )
        check(
            f"agent '{agent_id}' appears in registry after registration",
            agent_id in registered_agents,
        )

    # Step 2b: write the first runnable agent Todo. connect/boot no longer seeds
    # one, so the guided takeover frontier has to come from the caller.
    seeded_todo = run_cli(
        "--registry", str(registry_path),
        "todo", "add",
        "--goal-id", goal_id,
        "--role", "agent",
        "--text", "[P0] Implement the first bounded regression segment.",
        "--task-class", "advancement_task",
        "--action-kind", "implementation",
        "--claimed-by", agent_id,
        "--execute",
        check=False,
    )
    check("first agent todo exits 0", seeded_todo.returncode == 0)

    # Step 3: Build the guided packet via direct Python import.
    guided_packet = build_start_goal_guided_packet(
        project=project,
        goal_id=goal_id,
        agent_id=agent_id,
        cli_bin="loopx",
        host_surface="claude-code",
        goal_text="regression test for #3092",
    )
    # The fixture seeds one runnable advancement Todo, so this must not accept
    # the frontier-free legacy authoring path.
    template = _require_guided_todo_delta_template(
        guided_packet,
        label="guided packet",
    )

    # Defect 1 core assertion: template must use --claimed-by, not --agent-id.
    check(
        "template does NOT contain --agent-id",
        "--agent-id" not in template,
    )
    check(
        "template contains --claimed-by",
        "--claimed-by" in template,
    )

    print("\n=== Scenario 3: todo add with --claimed-by accepted ===")

    # Run a concrete todo add using the correct --claimed-by pattern.
    todo_result = run_cli(
        "--registry", str(registry_path),
        "todo", "add",
        "--goal-id", goal_id,
        "--project", str(project),
        "--role", "agent",
        "--claimed-by", agent_id,
        "--task-class", "advancement_task",
        "--action-kind", "verify",
        "--text", "[P0] regression guard for #3092",
        check=False,
    )
    check("todo add exits 0", todo_result.returncode == 0)
    try:
        todo_payload = json.loads(todo_result.stdout)
    except (json.JSONDecodeError, ValueError):
        todo_payload = {}
    check("todo add returns ok: true", todo_payload.get("ok") is True)
    check(
        "todo add returns a todo_id",
        bool(todo_payload.get("todo_id")),
    )


# ---------------------------------------------------------------------------
# Scenario 4: agent-onboard after bootstrap returns a real packet
# ---------------------------------------------------------------------------
def test_post_bootstrap_onboard(project: Path) -> None:
    print("\n=== Scenario 4: agent-onboard after bootstrap (happy path) ===")

    result = run_cli(
        "agent-onboard",
        "--agent-type", "claude-code",
        "--project", str(project),
        check=False,
    )
    check(
        "post-bootstrap agent-onboard has no traceback",
        "FileNotFoundError" not in (result.stderr + result.stdout),
    )
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    check("post-bootstrap agent-onboard returns valid JSON", bool(payload))
    # After bootstrap the packet should be a structured response, not a crash.
    check(
        "post-bootstrap agent-onboard returns a structured packet",
        isinstance(payload, dict) and len(payload) > 0,
    )


# ---------------------------------------------------------------------------
# Scenario 5: clean second run in a fresh temp dir
# ---------------------------------------------------------------------------
def test_clean_second_run() -> None:
    print("\n=== Scenario 5: clean second run (no state leakage) ===")

    with tempfile.TemporaryDirectory(prefix="loopx-3092-second-") as tmp:
        project = Path(tmp) / "project-second"
        project.mkdir()
        goal_id = "second-run-goal"
        agent_id = "second-agent"

        # Repeat the unconnected onboard check in a clean directory.
        result = run_cli(
            "agent-onboard",
            "--agent-type", "claude-code",
            "--project", str(project),
            check=False,
        )
        check(
            "second-run: agent-onboard on bare project has no traceback",
            "FileNotFoundError" not in (result.stderr + result.stdout),
        )
        try:
            second_payload = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            second_payload = {}
        second_identity_gate = second_payload.get("identity_selection_gate")
        check(
            "second-run: agent-onboard returns typed response (not crash)",
            second_payload.get("gate") == "project_not_connected"
            or second_payload.get("ok") is False
            or second_payload.get("connection_state") == "not_connected"
            or (
                isinstance(second_identity_gate, dict)
                and second_identity_gate.get("activation_allowed") is False
            ),
        )

        # Bootstrap + register + guided template check.
        run_cli(
            "bootstrap",
            "--project", str(project),
            "--goal-id", goal_id,
            "--objective", "second run regression",
            "--adapter-kind", "read_only_project_map_v0",
            "--adapter-status", "connected-read-only",
            "--no-global-sync",
            check=False,
        )
        registry_path = project / ".loopx" / "registry.json"
        if registry_path.exists():
            _register_agent_in_registry(registry_path, goal_id, agent_id)
            run_cli(
                "--registry", str(registry_path),
                "todo", "add",
                "--goal-id", goal_id,
                "--role", "agent",
                "--text", "[P0] Implement the second-run bounded segment.",
                "--task-class", "advancement_task",
                "--action-kind", "implementation",
                "--claimed-by", agent_id,
                "--execute",
                check=False,
            )

        guided = build_start_goal_guided_packet(
            project=project,
            goal_id=goal_id,
            agent_id=agent_id,
            cli_bin="loopx",
            host_surface="claude-code",
            goal_text="second run check",
        )
        template = _require_guided_todo_delta_template(
            guided,
            label="second-run guided packet",
        )
        check(
            "second-run: template uses --claimed-by",
            "--claimed-by" in template,
        )
        check(
            "second-run: template does not use --agent-id",
            "--agent-id" not in template,
        )

        if registry_path.exists():
            todo_result = run_cli(
                "--registry", str(registry_path),
                "todo", "add",
                "--goal-id", goal_id,
                "--project", str(project),
                "--role", "agent",
                "--claimed-by", agent_id,
                "--task-class", "advancement_task",
                "--action-kind", "implement",
                "--text", "[P1] second-run guard",
                check=False,
            )
            try:
                todo_payload = json.loads(todo_result.stdout)
            except (json.JSONDecodeError, ValueError):
                todo_payload = {}
            check(
                "second-run: todo add with --claimed-by returns ok",
                todo_payload.get("ok") is True,
            )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-3092-regression-") as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        goal_id = "regression-3092"

        # Scenario 1: unconnected project — must not crash.
        test_unconnected_agent_onboard(project)

        # Scenarios 2 & 3: bootstrap, register, guided template, todo add.
        test_guided_template_acceptance(project, goal_id)

        # Scenario 4: onboard after bootstrap — must succeed.
        test_post_bootstrap_onboard(project)

    # Scenario 5: isolated second run in a fresh temp dir.
    test_clean_second_run()

    print(f"\n{'=' * 50}")
    print(f"fresh-project-onboarding-regression-smoke: PASS={PASS}  FAIL={FAIL}")
    if FAIL:
        print("SOME CHECKS FAILED — see above for details.")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
