from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from loopx import goal_mode_mcp
from loopx import cli as loopx_cli
from loopx.claude_goal_mode.hooks.goal_state import goal_context as claude_context
from loopx.goal_mode_mcp import (
    GoalModeMCPConfig,
    GoalModeMCPControlPlane,
    create_fastmcp_server,
)
from loopx.kunluncode_goal_mode import cli
from loopx.kunluncode_goal_mode.app_server import (
    NATIVE_GOAL_MODES,
    KunlunAppServerError,
    native_goal_success,
    stable_text_digest,
)
from loopx.kunluncode_goal_mode.context import (
    goal_context as kunluncode_context,
    write_binding,
)
from loopx.kunluncode_goal_mode.guards import (
    NATIVE_CONTROLLER_AGENT_ENV,
    NATIVE_CONTROLLER_ENV,
    NATIVE_CONTROLLER_GOAL_ENV,
    guard_native_controller_writeback,
    native_controller_cli_write_block,
)
from loopx.kunluncode_goal_mode.runtime import (
    RUNTIME_STATE_SCHEMA_VERSION,
    KunlunNativeGoalRuntimeError,
    build_native_goal_objective,
    read_runtime_state,
    run_native_goal,
    write_runtime_state,
)


def _registry(project: Path) -> Path:
    path = project / ".loopx" / "registry.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "goals": [
                    {
                        "id": "shared-goal",
                        "repo": str(project),
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": ["cc", "kunlun"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_claude_and_kunluncode_bind_distinct_agents(tmp_path: Path) -> None:
    _registry(tmp_path)
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    claude_dir.joinpath("loop.md").write_text(
        '<!-- loopx:armed {"goal_id":"shared-goal","agent_id":"cc"} -->\n',
        encoding="utf-8",
    )
    write_binding(tmp_path, goal_id="shared-goal", agent_id="kunlun")

    claude = claude_context(tmp_path)
    kunlun = kunluncode_context(tmp_path)

    assert claude and claude["agent_id"] == "cc"
    assert kunlun and kunlun["agent_id"] == "kunlun"
    assert claude["goal_id"] == kunlun["goal_id"] == "shared-goal"


def test_kunluncode_binding_fails_closed_for_unregistered_agent(tmp_path: Path) -> None:
    _registry(tmp_path)
    write_binding(tmp_path, goal_id="shared-goal", agent_id="not-registered")

    assert kunluncode_context(tmp_path) is None


def test_mcp_uses_kunluncode_profile_and_rejects_agent_impersonation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    control = GoalModeMCPControlPlane(
        GoalModeMCPConfig(
            server_name="loopx-kunluncode",
            runtime_profile="kunluncode",
            legacy_host_surface="kunluncode",
        ),
        lambda: {
            "goal_id": "shared-goal",
            "registry": "/project/.loopx/registry.json",
            "agent_id": "kunlun",
        },
    )
    commands: list[list[str]] = []
    control.command_prefix = lambda: ["loopx"]

    def capture(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, '{"ok": true}', "")

    monkeypatch.setattr(goal_mode_mcp.subprocess, "run", capture)

    assert json.loads(control.claim_task("todo-1", "cc"))["ok"] is False
    assert commands == []

    assert json.loads(control.should_run())["ok"] is True
    assert commands[-1][-2:] == ["--runtime-profile", "kunluncode"]

    assert json.loads(control.claim_task("todo-1", "kunlun"))["ok"] is True
    assert commands[-1][-4:] == ["--claimed-by", "kunlun", "--agent-id", "kunlun"]

    output = control.complete_task(
        "todo-1",
        "kunlun",
        "focused check passed",
        no_follow_up=True,
    )
    assert "spend-slot" in output
    assert "--no-follow-up" in commands[-2]
    assert commands[-1][-2:] == ["--agent-id", "kunlun"]


def test_installer_registers_only_the_owned_global_mcp_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(cli, "_compatible_python", lambda _python: True)
    monkeypatch.setattr(cli, "_configured_mcp_servers", lambda _binary: [])

    def capture(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(cli, "_run", capture)

    selected = cli.install_mcp(
        python="/managed/.venv/bin/python",
        dry_run=False,
        replace=False,
    )

    assert selected == "/managed/.venv/bin/python"
    assert calls == [
        [
            "/usr/bin/kunluncode",
            "mcp",
            "add",
            "loopx-kunluncode",
            "--command",
            "/managed/.venv/bin/python",
            "--args",
            str(cli.MCP_SCRIPT),
        ]
    ]


def test_installer_refuses_to_replace_a_foreign_named_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(cli, "_compatible_python", lambda _python: True)
    monkeypatch.setattr(
        cli,
        "_configured_mcp_servers",
        lambda _binary: [
            {
                "name": "loopx-kunluncode",
                "command": "/user/custom-server",
                "args": [],
            }
        ],
    )

    with pytest.raises(RuntimeError, match="user-owned"):
        cli.install_mcp(
            python="/managed/.venv/bin/python",
            dry_run=False,
            replace=False,
        )


def test_installer_normalizes_relative_python_to_an_absolute_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    interpreter = tmp_path / ".venv" / "bin" / "python"
    calls: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(cli, "_compatible_python", lambda _python: True)
    monkeypatch.setattr(cli, "_configured_mcp_servers", lambda _binary: [])

    def capture(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(cli, "_run", capture)

    selected = cli.install_mcp(
        python=".venv/bin/python",
        dry_run=False,
        replace=False,
    )

    assert selected == str(interpreter)
    assert str(interpreter) in calls[0]


def test_connect_preserves_existing_registered_agents(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(cli, "_loopx_prefix", lambda: ["loopx"])

    def capture(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, '{"ok": true}', "")

    monkeypatch.setattr(cli, "_run", capture)

    result = cli.connect_project(
        project=tmp_path,
        goal_id="shared-goal",
        agent_id="kunlun-next",
        objective=None,
        python=None,
        skip_mcp=True,
        replace=False,
        dry_run=False,
    )

    configure = commands[0]
    registered = [
        configure[index + 1]
        for index, argument in enumerate(configure)
        if argument == "--registered-agent"
    ]
    assert registered == ["cc", "kunlun", "kunlun-next"]
    assert result["agent_id"] == "kunlun-next"
    assert json.loads(registry.read_text(encoding="utf-8"))["agent_backends"] == [
        "kunluncode"
    ]


def test_add_todo_assigns_without_impersonating_the_bound_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: list[str] = []
    monkeypatch.setattr(
        cli,
        "goal_context",
        lambda _project: {
            "goal_id": "shared-goal",
            "agent_id": "kunlun",
            "registry": str(tmp_path / ".loopx" / "registry.json"),
        },
    )
    monkeypatch.setattr(cli, "_loopx_prefix", lambda: ["loopx"])

    def capture(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(
            command,
            0,
            '{"ok": true, "todo_id": "todo-1"}',
            "",
        )

    monkeypatch.setattr(cli, "_run", capture)

    result = cli.add_todo(tmp_path, "Run the native protocol smoke")

    assert result["todo_id"] == "todo-1"
    assert captured[-2:] == ["--claimed-by", "kunlun"]
    assert "--agent-id" not in captured


def test_worker_prompt_closes_each_bounded_lifecycle_segment() -> None:
    prompt = cli.worker_prompt("kunlun")

    assert "should_run first" in prompt
    assert "claim exactly the selected todo" in prompt
    assert "complete_task" in prompt
    assert "no_follow_up=true" in prompt
    assert "never reuse the completed todo_id" in prompt
    assert "Re-check should_run once and stop" in prompt


def test_worker_prepends_the_adapter_environment_to_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cli,
        "goal_context",
        lambda _project: {"goal_id": "g", "agent_id": "kunlun"},
    )
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/kunluncode")

    def capture(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(cli.subprocess, "run", capture)

    assert (
        cli.run_worker(
            tmp_path,
            permission_mode="auto",
            max_duration_secs=60,
            json_output=True,
            dry_run=False,
            mode="headless",
        )
        == 0
    )

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["PATH"].split(":", 1)[0] == str(
        Path(cli.sys.executable).absolute().parent
    )


class _FakeControlPlane:
    def __init__(self, todo: dict[str, object]) -> None:
        self.todo = todo
        self.calls: list[str] = []
        self.ledger: list[dict[str, object]] = []

    def should_run(self) -> dict[str, object]:
        self.calls.append("should_run")
        return {"ok": True, "should_run": True, "selected_todo": self.todo}

    def claim(self, todo_id: str) -> dict[str, object]:
        self.calls.append(f"claim:{todo_id}")
        return {"ok": True, "todo_id": todo_id, "changed": True}

    def evidence_since(self, _since: str) -> dict[str, object]:
        self.calls.append("evidence_since")
        return {"ok": True, "ledger": list(self.ledger)}

    def record_verified_delivery(self, *, mode: str) -> dict[str, object]:
        self.calls.append(f"record:{mode}")
        return {
            "ok": True,
            "appended": True,
            "classification": f"kunluncode_native_{mode}_verified",
            "generated_at": "2026-08-05T00:00:01Z",
        }

    def complete(self, todo_id: str, *, evidence: str) -> dict[str, object]:
        assert "status=complete" in evidence
        self.calls.append(f"complete:{todo_id}")
        return {
            "ok": True,
            "completed": True,
            "todo_id": todo_id,
            "status": "done",
            "status_changed": True,
            "changed": True,
        }

    def spend(self) -> dict[str, object]:
        self.calls.append("spend")
        return {
            "ok": True,
            "appended": True,
            "classification": "quota_slot_spent",
            "generated_at": "2026-08-05T00:00:02Z",
            "slots": 1,
        }


class _FakeAppServer:
    def __init__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        event_handler,
        terminal_goal: dict[str, object] | None = None,
        resumed_goal: dict[str, object] | None = None,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.env = env
        self.event_handler = event_handler
        self.terminal_goal = terminal_goal
        self.resumed_goal = resumed_goal
        self.calls: list[str] = []
        self.objective = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def initialize(self) -> dict[str, object]:
        self.calls.append("initialize")
        return {"protocolVersion": "2026-07-27"}

    def start_thread(self, _project: Path) -> str:
        self.calls.append("start_thread")
        return "thread-1"

    def resume_thread(self, thread_id: str) -> dict[str, object]:
        self.calls.append(f"resume:{thread_id}")
        return {"thread": {"id": thread_id}}

    def set_goal(
        self,
        _thread_id: str,
        *,
        objective: str,
        mode: str,
        token_budget: int | None = None,
    ) -> dict[str, object]:
        del token_budget
        self.calls.append(f"set_goal:{mode}")
        self.objective = objective
        return {
            "goalId": "native-goal-1",
            "revision": 0,
            "mode": NATIVE_GOAL_MODES[mode],
            "verificationKind": "artifact",
            "status": "active",
            "objective": objective,
            "events": [],
        }

    def get_goal(self, _thread_id: str) -> dict[str, object]:
        self.calls.append("get_goal")
        if self.resumed_goal is None:
            raise AssertionError("unexpected get_goal")
        self.objective = str(self.resumed_goal.get("objective") or "")
        return dict(self.resumed_goal)

    def start_turn(self, _thread_id: str, _prompt: str) -> dict[str, object]:
        self.calls.append("start_turn")
        self.event_handler({"method": "turn/started", "params": {}})
        return {"turn": {"id": "turn-1", "status": "running"}}

    def wait_for_goal_terminal(
        self,
        _thread_id: str,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        assert timeout_seconds > 0
        self.calls.append("wait_terminal")
        self.event_handler({"method": "turn/completed", "params": {}})
        if self.terminal_goal is not None:
            goal = dict(self.terminal_goal)
            goal.setdefault("objective", self.objective)
            return goal
        return {
            "goalId": "native-goal-1",
            "revision": 2,
            "mode": "strict",
            "verificationKind": "artifact",
            "status": "complete",
            "objective": self.objective,
            "events": [
                {"kind": "verification_passed"},
                {"kind": "complete"},
            ],
        }


def _native_context(tmp_path: Path) -> dict[str, str]:
    return {
        "goal_id": "shared-goal",
        "agent_id": "kunlun",
        "registry": str(tmp_path / ".loopx" / "registry.json"),
    }


def _native_todo(*, claimed: bool = False) -> dict[str, object]:
    return {
        "todo_id": "todo-native-1",
        "text": "Implement and verify the native Goal Pro adapter.",
        "claimed_by": "kunlun" if claimed else "",
        "required_write_scopes": ["loopx/kunluncode_goal_mode/**"],
    }


def _native_state(
    todo: dict[str, object],
    *,
    thread_id: str = "thread-1",
    verified: bool = False,
) -> dict[str, object]:
    objective = build_native_goal_objective(todo, agent_id="kunlun")
    return {
        "schema_version": RUNTIME_STATE_SCHEMA_VERSION,
        "created_at": "2026-08-05T00:00:00Z",
        "updated_at": "2026-08-05T00:00:00Z",
        "binding": {"goal_id": "shared-goal", "agent_id": "kunlun"},
        "todo_id": "todo-native-1",
        "native": {
            "mode": "goal-pro",
            "objective_sha256": stable_text_digest(objective),
            "thread_id": thread_id,
            "goal_id": "native-goal-1",
            "revision": 2 if verified else 0,
            "status": "complete" if verified else "active",
            "verification_kind": "artifact",
            "verification_passed": verified,
            "verified": verified,
            "verified_at": "2026-08-05T00:00:00Z" if verified else None,
            "resumed": False,
            "event_counts": {},
        },
        "writeback": {
            "delivery_recorded": False,
            "todo_completed": False,
            "quota_spent": False,
        },
    }


def test_strict_native_goal_requires_verification_passed_event() -> None:
    accepted = {
        "status": "complete",
        "mode": "strict",
        "events": [{"kind": "verification_passed"}, {"kind": "complete"}],
    }
    rejected = {
        "status": "complete",
        "mode": "strict",
        "events": [{"kind": "complete"}],
    }

    assert native_goal_success(accepted, mode="goal-pro") is True
    assert native_goal_success(rejected, mode="goal-pro") is False
    assert (
        native_goal_success(
            {"status": "complete", "mode": "arrangement", "events": []},
            mode="goal",
        )
        is True
    )


def test_native_controller_blocks_model_visible_mcp_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, control = create_fastmcp_server(
        GoalModeMCPConfig(
            server_name="loopx-kunluncode-test",
            runtime_profile="kunluncode",
            legacy_host_surface="kunluncode",
        ),
        lambda: {
            "goal_id": "shared-goal",
            "registry": "/project/.loopx/registry.json",
            "agent_id": "kunlun",
        },
    )
    monkeypatch.setenv(NATIVE_CONTROLLER_ENV, "1")

    guard_native_controller_writeback(control)

    claim_content, _ = asyncio.run(
        server.call_tool(
            "claim_task",
            {"todo_id": "todo-1", "agent_id": "kunlun"},
        )
    )
    complete_content, _ = asyncio.run(
        server.call_tool(
            "complete_task",
            {
                "todo_id": "todo-1",
                "agent_id": "kunlun",
                "evidence": "premature evidence",
            },
        )
    )

    assert json.loads(claim_content[0].text)["ok"] is False
    assert json.loads(complete_content[0].text)["ok"] is False


def test_native_controller_blocks_direct_cli_write_to_the_bound_goal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(NATIVE_CONTROLLER_ENV, "1")
    monkeypatch.setenv(NATIVE_CONTROLLER_GOAL_ENV, "shared-goal")
    monkeypatch.setenv(NATIVE_CONTROLLER_AGENT_ENV, "kunlun")

    exit_code = loopx_cli.main(
        [
            "--format",
            "json",
            "todo",
            "complete",
            "--goal-id",
            "shared-goal",
            "--todo-id",
            "todo-1",
            "--claimed-by",
            "kunlun",
            "--agent-id",
            "kunlun",
            "--evidence",
            "premature evidence",
            "--no-follow-up",
        ]
    )

    payload = json.loads(capsys.readouterr().err)
    assert exit_code == 2
    assert payload["error_code"] == "kunluncode_outer_controller_write_owned"
    assert payload["operation"] == "todo complete"
    assert payload["goal_id"] == "shared-goal"


def test_native_controller_cli_guard_preserves_reads_and_other_goals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(NATIVE_CONTROLLER_ENV, "1")
    monkeypatch.setenv(NATIVE_CONTROLLER_GOAL_ENV, "shared-goal")
    monkeypatch.setenv(NATIVE_CONTROLLER_AGENT_ENV, "kunlun")

    assert (
        native_controller_cli_write_block(
            SimpleNamespace(
                command="quota",
                quota_command="should-run",
                goal_id="shared-goal",
            )
        )
        is None
    )
    assert (
        native_controller_cli_write_block(
            SimpleNamespace(
                command="todo",
                todo_command="complete",
                goal_id="another-goal",
            )
        )
        is None
    )
    retirement = native_controller_cli_write_block(
        SimpleNamespace(
            command="retire-global-goal",
            goal_id=["shared-goal"],
        )
    )
    assert retirement is not None
    assert retirement["operation"] == "retire-global-goal"


def test_native_goal_pro_commits_only_after_verified_terminal_state(
    tmp_path: Path,
) -> None:
    control = _FakeControlPlane(_native_todo())
    clients: list[_FakeAppServer] = []

    def factory(command: list[str], **kwargs) -> _FakeAppServer:
        client = _FakeAppServer(command, **kwargs)
        clients.append(client)
        return client

    result = run_native_goal(
        tmp_path,
        _native_context(tmp_path),
        mode="goal-pro",
        permission_mode="auto",
        max_duration_secs=60,
        controller_timeout_secs=120,
        kunluncode_bin="/usr/bin/kunluncode",
        control_plane=control,
        client_factory=factory,
    )

    assert result["status"] == "committed"
    assert control.calls == [
        "should_run",
        "claim:todo-native-1",
        "evidence_since",
        "record:goal-pro",
        "complete:todo-native-1",
        "spend",
    ]
    assert clients[0].calls == [
        "initialize",
        "start_thread",
        "set_goal:goal-pro",
        "start_turn",
        "wait_terminal",
    ]
    assert clients[0].env[NATIVE_CONTROLLER_ENV] == "1"
    assert clients[0].env[NATIVE_CONTROLLER_GOAL_ENV] == "shared-goal"
    assert clients[0].env[NATIVE_CONTROLLER_AGENT_ENV] == "kunlun"
    state = read_runtime_state(tmp_path)
    assert state is not None
    assert state["native"]["verified"] is True
    assert state["writeback"]["quota_spent"] is True
    journal = (tmp_path / ".loopx" / "kunluncode-runtime.json").read_text()
    assert "Implement and verify the native Goal Pro adapter" not in journal


def test_native_goal_reconciles_crash_after_writeback_without_repeating_it(
    tmp_path: Path,
) -> None:
    todo = _native_todo(claimed=True)
    control = _FakeControlPlane(todo)
    state = _native_state(todo, verified=True)
    write_runtime_state(tmp_path, state)
    control.ledger = [
        {
            "event_kind": "refresh_state",
            "classification": "kunluncode_native_goal_pro_verified",
        },
        {"event_kind": "todo_complete", "todo_id": "todo-native-1"},
        {"event_kind": "quota_spend"},
    ]

    def forbidden_factory(*_args, **_kwargs):
        raise AssertionError("verified recovery must not relaunch KunlunCode")

    result = run_native_goal(
        tmp_path,
        _native_context(tmp_path),
        mode="goal-pro",
        permission_mode="auto",
        max_duration_secs=60,
        controller_timeout_secs=120,
        kunluncode_bin="/usr/bin/kunluncode",
        control_plane=control,
        client_factory=forbidden_factory,
    )

    assert result["recovered"] is True
    assert control.calls == ["evidence_since"]
    recovered = read_runtime_state(tmp_path)
    assert recovered is not None
    assert recovered["writeback"]["delivery_recorded"] is True
    assert recovered["writeback"]["todo_completed"] is True
    assert recovered["writeback"]["quota_spent"] is True


def test_native_goal_resumes_the_same_thread_and_goal_after_interruption(
    tmp_path: Path,
) -> None:
    todo = _native_todo(claimed=True)
    control = _FakeControlPlane(todo)
    objective = build_native_goal_objective(todo, agent_id="kunlun")
    state = _native_state(todo, thread_id="thread-existing")
    write_runtime_state(tmp_path, state)
    clients: list[_FakeAppServer] = []

    def factory(command: list[str], **kwargs) -> _FakeAppServer:
        client = _FakeAppServer(
            command,
            **kwargs,
            resumed_goal={
                "goalId": "native-goal-1",
                "revision": 0,
                "mode": "strict",
                "verificationKind": "artifact",
                "status": "active",
                "objective": objective,
                "events": [],
            },
        )
        clients.append(client)
        return client

    result = run_native_goal(
        tmp_path,
        _native_context(tmp_path),
        mode="goal-pro",
        permission_mode="auto",
        max_duration_secs=60,
        controller_timeout_secs=120,
        kunluncode_bin="/usr/bin/kunluncode",
        control_plane=control,
        client_factory=factory,
    )

    assert result["status"] == "committed"
    assert result["recovered"] is True
    assert clients[0].calls[:3] == [
        "initialize",
        "resume:thread-existing",
        "get_goal",
    ]
    assert "start_thread" not in clients[0].calls
    assert "set_goal:goal-pro" not in clients[0].calls


def test_native_goal_does_not_duplicate_work_when_recorded_thread_cannot_resume(
    tmp_path: Path,
) -> None:
    todo = _native_todo(claimed=True)
    control = _FakeControlPlane(todo)
    write_runtime_state(tmp_path, _native_state(todo, thread_id="thread-existing"))
    clients: list[_FakeAppServer] = []

    class UnavailableThreadAppServer(_FakeAppServer):
        def resume_thread(self, thread_id: str) -> dict[str, object]:
            self.calls.append(f"resume:{thread_id}")
            raise KunlunAppServerError("recorded thread is unavailable")

    def factory(command: list[str], **kwargs) -> _FakeAppServer:
        client = UnavailableThreadAppServer(command, **kwargs)
        clients.append(client)
        return client

    with pytest.raises(KunlunAppServerError, match="recorded thread is unavailable"):
        run_native_goal(
            tmp_path,
            _native_context(tmp_path),
            mode="goal-pro",
            permission_mode="auto",
            max_duration_secs=60,
            controller_timeout_secs=120,
            kunluncode_bin="/usr/bin/kunluncode",
            control_plane=control,
            client_factory=factory,
        )

    assert clients[0].calls == ["initialize", "resume:thread-existing"]
    assert not any(call.startswith("record:") for call in control.calls)
    assert not any(call.startswith("complete:") for call in control.calls)
    assert "spend" not in control.calls


def test_native_goal_pro_rejects_complete_without_verifier_pass(
    tmp_path: Path,
) -> None:
    control = _FakeControlPlane(_native_todo(claimed=True))
    clients: list[_FakeAppServer] = []

    def factory(command: list[str], **kwargs) -> _FakeAppServer:
        client = _FakeAppServer(
            command,
            **kwargs,
            terminal_goal={
                "goalId": "native-goal-1",
                "revision": 1,
                "mode": "strict",
                "verificationKind": "artifact",
                "status": "complete",
                "events": [{"kind": "complete"}],
            },
        )
        clients.append(client)
        return client

    with pytest.raises(KunlunNativeGoalRuntimeError, match="accepted terminal"):
        run_native_goal(
            tmp_path,
            _native_context(tmp_path),
            mode="goal-pro",
            permission_mode="auto",
            max_duration_secs=60,
            controller_timeout_secs=120,
            kunluncode_bin="/usr/bin/kunluncode",
            control_plane=control,
            client_factory=factory,
        )

    assert "record:goal-pro" not in control.calls
    assert "complete:todo-native-1" not in control.calls
    assert "spend" not in control.calls
    state = read_runtime_state(tmp_path)
    assert state is not None
    assert state["native"]["status"] == "complete"
    assert state["native"]["verified"] is False
