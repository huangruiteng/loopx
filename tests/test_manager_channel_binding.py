"""The steward channel resolves one disclosed default for its executor and model."""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from loopx.chat_agent import CodexChatAgentError
from loopx.capabilities.manager_runtime import manager_runtime_capability_projection
from loopx.chat_manager import (
    MANAGER_ENDPOINT_MANAGED,
    MANAGER_ENDPOINT_DEFAULT_REASON_STEWARD_CHANNEL_DEFAULT,
    MANAGER_ENDPOINT_SOURCE_EXPLICIT_CONFIG,
    MANAGER_ENDPOINT_SOURCE_PRODUCT_DEFAULT,
    MANAGER_MODEL_SOURCE_MANAGED_PROFILE,
    MANAGER_MODEL_SOURCE_ENV_OVERRIDE,
    MANAGER_MODEL_SOURCE_VENDOR_DEFAULT,
    MANAGER_CHANNEL_SESSION_MODE_SOURCE_READBACK,
    MANAGER_CHANNEL_SESSION_MODE_SOURCE_UNBOUND,
    MANAGER_CHANNEL_SESSION_MODE_SOURCE_UNRECOGNIZED,
    manager_channel_session,
    manager_channel_session_mode_readback,
    manager_endpoint_default_reason,
    manager_channel_binding,
    manager_executor_endpoint_default,
    manager_model_config,
    open_manager_session,
    selected_manager_executor_endpoint,
)
from loopx.chat_runtime import ChatRuntimeController
from loopx.chat_server import ChatHTTPServer, ChatRequestHandler
from loopx.chat_store import ChatSessionStore
from loopx.control_plane.turn_driver import host_binding
from loopx.extensions.lark.cli_resolution import LarkCliResolution


def test_the_shipped_default_is_the_cli_endpoint_on_every_machine():
    """A machine with only a personal login must keep a reachable steward."""

    binding = manager_channel_binding({})

    assert (
        binding["executor_endpoint"] == manager_executor_endpoint_default({}) == "codex"
    )
    assert (
        binding["executor_endpoint_source"] == MANAGER_ENDPOINT_SOURCE_PRODUCT_DEFAULT
    )
    assert (
        binding["executor_endpoint_default_reason"]
        == manager_endpoint_default_reason({})
        == MANAGER_ENDPOINT_DEFAULT_REASON_STEWARD_CHANNEL_DEFAULT
    )
    assert binding["executor_kind"] == "individual"
    assert binding["credential_env_var"] == ""
    assert binding["operator_credential_configured"] is False
    assert binding["execution_profile"] is None
    assert binding["available"] is None
    assert binding["unavailable_reason"] is None
    assert binding["model"] == "gpt-6-astra"
    assert binding["model_source"] == MANAGER_MODEL_SOURCE_VENDOR_DEFAULT


def test_the_operator_credential_authenticates_without_selecting_the_executor():
    """A credential authenticates a configuration; it never picks one.

    The steward is the surface a person talks to, so discovering an operator
    credential must not re-point it in the middle of a conversation -- and it
    must not hand the interactive channel an operator model to run through an
    individual CLI login either.
    """

    with_credential = manager_channel_binding({"DEEPSEEK_API_KEY": "fixture"})

    assert (
        with_credential["executor_endpoint"]
        == manager_executor_endpoint_default({"DEEPSEEK_API_KEY": "fixture"})
        == "codex"
    )
    assert (
        with_credential["executor_endpoint_source"]
        == MANAGER_ENDPOINT_SOURCE_PRODUCT_DEFAULT
    )
    assert (
        with_credential["executor_endpoint_default_reason"]
        == MANAGER_ENDPOINT_DEFAULT_REASON_STEWARD_CHANNEL_DEFAULT
    )
    # The model follows the executor the channel runs, so a configured
    # credential cannot leave a managed model pointed at an individual CLI.
    assert with_credential["executor_kind"] == "individual"
    assert with_credential["model"] == "gpt-6-astra"
    assert with_credential["model_source"] == MANAGER_MODEL_SOURCE_VENDOR_DEFAULT
    assert with_credential["execution_profile"] is None
    # The credential is still reported as the fact it is, by variable name and
    # never by value, so an operator can see it was seen.
    assert with_credential["operator_credential_configured"] is True
    assert with_credential["credential_env_var"] == ""
    assert "fixture" not in json.dumps(with_credential)


def test_selecting_the_managed_host_runs_the_managed_execution_profile(monkeypatch):
    """Selection, not discovery, is what puts the channel on the managed host."""

    monkeypatch.setattr(
        host_binding, "dsh_runtime_importable", lambda *args, **kwargs: True
    )

    selected = manager_channel_binding(
        {"LOOPX_MANAGER_ENDPOINT": "dsh", "DEEPSEEK_API_KEY": "fixture"}
    )

    assert selected["executor_endpoint"] == MANAGER_ENDPOINT_MANAGED == "dsh"
    assert selected["executor_endpoint_source"] == MANAGER_ENDPOINT_SOURCE_EXPLICIT_CONFIG
    # An explicit selection carries no shipped-default reason to explain.
    assert selected["executor_endpoint_default_reason"] == ""
    assert selected["executor_kind"] == "managed"
    assert selected["available"] is True
    # The model follows the executor: the managed host runs the same execution
    # profile a governed Turn runs, so the channel and its workers agree.
    assert selected["model"] == "deepseek-v4-flash"
    assert selected["model_source"] == MANAGER_MODEL_SOURCE_MANAGED_PROFILE
    # One line, the same shape the governed Turn readback publishes, so the
    # channel and its workers cannot report two different managed profiles.
    assert selected["execution_profile"] == "deepseek-v4-flash@high"
    assert selected["credential_env_var"] == "DEEPSEEK_API_KEY"
    assert "fixture" not in json.dumps(selected)


def test_an_explicit_endpoint_selection_reports_no_default_reason():
    binding = manager_channel_binding(
        {"LOOPX_MANAGER_ENDPOINT": "codex", "DEEPSEEK_API_KEY": "fixture"}
    )

    # The operator selected the endpoint, so the projection must not claim a
    # shipped-default reason for the endpoint it resolved.
    assert binding["executor_endpoint"] == "codex"
    assert binding["executor_endpoint_source"] == MANAGER_ENDPOINT_SOURCE_EXPLICIT_CONFIG
    assert binding["executor_endpoint_default_reason"] == ""
    assert binding["model"] == "gpt-6-astra"
    assert binding["execution_profile"] is None


def test_an_explicit_endpoint_selection_wins_over_the_shipped_default():
    endpoint, source = selected_manager_executor_endpoint(
        {"LOOPX_MANAGER_ENDPOINT": "fixture-endpoint"}
    )

    assert (endpoint, source) == (
        "fixture-endpoint",
        MANAGER_ENDPOINT_SOURCE_EXPLICIT_CONFIG,
    )
    assert manager_executor_endpoint_default({"LOOPX_MANAGER_ENDPOINT": " "}) == "codex"


def test_selecting_the_managed_host_quotes_the_turn_executor_verdict():
    """The channel cannot advertise an executor the Turn driver would refuse."""

    binding = manager_channel_binding({"LOOPX_MANAGER_ENDPOINT": "dsh"})

    assert binding["executor_endpoint"] == "dsh"
    assert binding["executor_kind"] == "managed"
    assert binding["available"] is False
    # The blocking fact is the credential or a missing runtime, and either way
    # the channel fails closed instead of running on an unauthenticated host.
    assert binding["unavailable_reason"] in {
        "operator_credential_unconfigured",
        "dsh_runtime_unavailable",
    }
    # An operator-billed endpoint names the credential it authenticates with.
    assert binding["credential_env_var"] == ""
    assert (
        manager_channel_binding(
            {"LOOPX_MANAGER_ENDPOINT": "dsh", "DEEPSEEK_API_KEY": "fixture"}
        )["credential_env_var"]
        == "DEEPSEEK_API_KEY"
    )


def test_an_unknown_explicit_endpoint_makes_no_availability_claim():
    binding = manager_channel_binding({"LOOPX_MANAGER_ENDPOINT": "fixture-endpoint"})

    assert binding["executor_kind"] == ""
    assert binding["available"] is None
    assert binding["model"] == "gpt-6-astra"


def test_explicit_model_override_wins_on_either_endpoint():
    overridden = manager_channel_binding(
        {"DEEPSEEK_API_KEY": "fixture", "LOOPX_MANAGER_MODEL": "fixture-model"}
    )
    assert overridden["model"] == "fixture-model"
    assert overridden["model_source"] == MANAGER_MODEL_SOURCE_ENV_OVERRIDE

    assert manager_model_config(
        {"DEEPSEEK_API_KEY": "fixture", "LOOPX_MANAGER_MODEL": "fixture-model"}
    ) == {"model": "fixture-model", "reasoning_effort": "high"}
    assert manager_model_config({"LOOPX_MANAGER_REASONING_EFFORT": "low"}) == {
        "model": "gpt-6-astra",
        "reasoning_effort": "low",
    }
    # The managed effort is the same field the governed Turn surface resolves,
    # and it applies to the managed endpoint the operator selected.
    assert manager_model_config(
        {
            "LOOPX_MANAGER_ENDPOINT": "dsh",
            "DEEPSEEK_API_KEY": "fixture",
            "LOOPX_TURN_REASONING_EFFORT": "max",
        }
    ) == {"model": "deepseek-v4-flash", "reasoning_effort": "max"}
    # Selection is what moves the pair: the same credential without it leaves
    # the interactive endpoint on its own vendor model and effort.
    assert manager_model_config(
        {"DEEPSEEK_API_KEY": "fixture", "LOOPX_TURN_REASONING_EFFORT": "max"}
    ) == {"model": "gpt-6-astra", "reasoning_effort": "high"}


def test_manager_model_config_reads_the_process_environment(monkeypatch):
    monkeypatch.delenv("LOOPX_MANAGER_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert manager_model_config()["model"] == "gpt-6-astra"


def test_open_manager_session_resolves_the_endpoint_only_when_unset(tmp_path):
    calls: list[dict[str, object]] = []

    class Controller:
        def open_session(self, **kwargs):
            calls.append(kwargs)
            return {"session_id": "fixture"}, False

    controller = Controller()
    open_manager_session(controller=controller, goal_id="g", work_dir=tmp_path)
    assert calls[-1]["agent_id"] == manager_executor_endpoint_default()
    assert calls[-1]["mode"] == "resume_latest"

    open_manager_session(
        controller=controller,
        goal_id="g",
        work_dir=tmp_path,
        executor_endpoint_id="claude-code",
    )
    assert calls[-1]["agent_id"] == "claude-code"

    open_manager_session(
        controller=controller, goal_id="g", work_dir=tmp_path, mode="new"
    )
    assert calls[-1]["mode"] == "new"


def test_chat_entry_point_never_lets_a_client_default_pick_the_steward_executor(
    tmp_path, monkeypatch
):
    """The Codex App Chat server is an entry point, not the channel's owner.

    A client that ships with its own silent executor default must not be able to
    re-point the steward channel: only an explicit pick travels, and everything
    else resolves through the channel's own default. The Goal-scoped path keeps
    its own unchanged default.
    """

    calls: list[dict[str, object]] = []

    class Controller:
        def close(self) -> None:
            return None

        def open_session(self, **kwargs):
            calls.append(kwargs)
            agent_id = str(kwargs["agent_id"])
            return {
                "session_id": f"session-{len(calls)}",
                "goal_id": kwargs["goal_id"],
                "agent_id": agent_id,
                "executor_endpoint_id": agent_id,
                "adapter_kind": "fixture",
                "status": "ready",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "last_activity_at": "2026-01-01T00:00:00Z",
                "session_mode": "managed_runtime",
                "channel_id": str(kwargs.get("channel_id") or ""),
            }, False

    store = ChatSessionStore(tmp_path / "runtime")
    (tmp_path / "active.md").write_text(
        "# Fixture Goal\n\n## Objective\nFixture objective\n\n## Agent Todo\n\n## User Todo\n",
        encoding="utf-8",
    )
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": "fixture-goal",
                        "repo": str(tmp_path),
                        "state_file": "active.md",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    server = ChatHTTPServer(("127.0.0.1", 0), ChatRequestHandler)
    server.registry_path = registry
    server.runtime_root_override = None
    server.verbose = False
    server.selected_goal_id = ""
    server.chat_store = store
    server.runtime_controller = Controller()
    monkeypatch.setattr(
        "loopx.chat_manager.manager_executor_endpoint_default",
        lambda environ=None: MANAGER_ENDPOINT_MANAGED,
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f"http://127.0.0.1:{server.server_port}"

    def create_session(body: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{origin}/api/chat/sessions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Origin": origin},
        )
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    try:
        resolved = create_session({"context_kind": "manager"})
        assert calls[-1]["agent_id"] == MANAGER_ENDPOINT_MANAGED
        assert resolved["agent_id"] == MANAGER_ENDPOINT_MANAGED
        assert resolved["session"]["executor_endpoint_id"] == MANAGER_ENDPOINT_MANAGED

        explicit = create_session({"context_kind": "manager", "agent_id": "codex"})
        assert calls[-1]["agent_id"] == "codex"
        assert explicit["session"]["executor_endpoint_id"] == "codex"

        goal = create_session({"context_kind": "goal", "goal_id": "fixture-goal"})
        assert goal["agent_id"] == "codex"
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def _managed_endpoint_failure(tmp_path, monkeypatch, *, runtime_installed):
    """Open the managed endpoint with its availability probe pinned.

    Which typed reason appears must follow the fact under test, not whether the
    machine running the suite happens to have the dsh runtime installed, so the
    probe is pinned here instead of being read from the environment.
    """

    monkeypatch.setattr(
        host_binding,
        "dsh_runtime_importable",
        lambda *args, **kwargs: runtime_installed,
    )
    runtime = ChatRuntimeController(
        store=ChatSessionStore(tmp_path / "store"), codex_bin="fixture-codex"
    )
    try:
        with pytest.raises(CodexChatAgentError) as raised:
            runtime.open_session(
                goal_id="fixture-goal",
                agent_id="dsh",
                work_dir=tmp_path,
                objective="fixture",
                mode="new",
            )
    finally:
        runtime.close()
    return raised.value


def test_a_managed_host_without_a_credential_raises_the_credential_gate(
    tmp_path, monkeypatch
):
    # The runtime is present and no operator credential is: the fact that blocks
    # this launch is the credential, so the typed gate must name it.
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    error = _managed_endpoint_failure(tmp_path, monkeypatch, runtime_installed=True)

    assert error.error_code == "agent_endpoint_unavailable"
    assert error.gate["kind"] == "host_tool_gate"
    assert "DEEPSEEK_API_KEY" in error.gate["next_action"]


def test_a_managed_host_without_its_runtime_names_the_install_step(
    tmp_path, monkeypatch
):
    # The credential is configured and the runtime is missing, so the launch is
    # blocked by the runtime instead; the gate must name that repair, not the
    # credential the operator already set.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture")

    error = _managed_endpoint_failure(tmp_path, monkeypatch, runtime_installed=False)

    assert error.error_code == "agent_endpoint_unavailable"
    assert error.gate["kind"] == "host_tool_gate"
    assert "pip install" in error.gate["next_action"]


def test_unknown_endpoint_keeps_the_untyped_lookup_error(tmp_path):
    runtime = ChatRuntimeController(
        store=ChatSessionStore(tmp_path / "store"), codex_bin="fixture-codex"
    )
    try:
        with pytest.raises(ValueError, match="unknown Agent endpoint"):
            runtime.open_session(
                goal_id="fixture-goal",
                agent_id="not-a-registered-endpoint",
                work_dir=tmp_path,
                objective="fixture",
                mode="new",
            )
    finally:
        runtime.close()


def test_manager_capability_projection_carries_the_channel_binding():
    binding = manager_channel_binding({"DEEPSEEK_API_KEY": "fixture"})
    projection = manager_runtime_capability_projection(
        object(),
        {"model": "gpt-6-astra", "reasoning_effort": "high"},
        channel_binding=binding,
    )

    assert projection["scope"] == "owner_global"
    assert projection["channel_binding"] == binding
    assert "fixture" not in json.dumps(projection)


def test_manager_capability_projection_stays_unchanged_without_a_binding():
    projection = manager_runtime_capability_projection(
        object(), {"model": "gpt-6-astra", "reasoning_effort": "high"}
    )

    assert "channel_binding" not in projection
    assert projection["model"] == "gpt-6-astra"


def test_the_channel_quotes_the_session_mode_instead_of_deriving_it():
    """The endpoint says managed; the Session says which mode is serving it."""

    binding = manager_channel_binding(
        {"LOOPX_MANAGER_ENDPOINT": "dsh", "DEEPSEEK_API_KEY": "fixture"},
        session={"session_mode": "attached_host", "status": "busy"},
    )

    assert binding["executor_endpoint"] == MANAGER_ENDPOINT_MANAGED
    assert binding["executor_kind"] == "managed"
    assert binding["session_mode"] == "attached_host"
    assert binding["session_mode_source"] == (
        MANAGER_CHANNEL_SESSION_MODE_SOURCE_READBACK
    )
    assert binding["session_status"] == "busy"


def test_a_channel_without_a_session_reads_as_unbound(monkeypatch):
    """A ready managed endpoint is not evidence that the channel is bound."""

    monkeypatch.setattr(
        host_binding, "dsh_runtime_importable", lambda *args, **kwargs: True
    )

    binding = manager_channel_binding(
        {"LOOPX_MANAGER_ENDPOINT": "dsh", "DEEPSEEK_API_KEY": "fixture"}
    )

    assert binding["available"] is True
    assert binding["session_mode"] is None
    assert binding["session_mode_source"] == (
        MANAGER_CHANNEL_SESSION_MODE_SOURCE_UNBOUND
    )
    assert binding["session_status"] is None


def test_an_unrecognized_session_mode_is_named_rather_than_coerced():
    """A mode outside the closed set is not rounded to the nearest known one."""

    readback = manager_channel_session_mode_readback(
        {"session_mode": "hybrid_handoff", "status": "ready"}
    )

    assert readback == {
        "session_mode": None,
        "session_mode_source": (
            MANAGER_CHANNEL_SESSION_MODE_SOURCE_UNRECOGNIZED
        ),
        "session_status": None,
    }


def test_the_channel_session_is_the_resumable_row_on_that_channel(tmp_path):
    """A closed Session leaves the channel unbound; another channel's is not it."""

    store = ChatSessionStore(tmp_path / "runtime")
    closed = store.create_session(
        goal_id="loopx-manager",
        agent_id="codex",
        adapter_kind="codex",
        upstream_thread_id="fixture-closed-host-session",
        channel_id="manager",
    )
    store.update_session(closed["session_id"], status="closed")
    elsewhere = store.create_session(
        goal_id="loopx-manager",
        agent_id="codex",
        adapter_kind="codex",
        upstream_thread_id="fixture-other-channel-host-session",
        channel_id="manager.external.fixture",
    )

    assert manager_channel_session(store) is None
    assert manager_channel_session(
        store, channel_id="manager.external.fixture"
    )["session_id"] == elsewhere["session_id"]

    attached = store.create_session(
        goal_id="loopx-manager",
        agent_id="codex",
        adapter_kind="codex",
        upstream_thread_id="fixture-attached-host-session",
        channel_id="manager",
        session_mode="attached_host",
        host_surface="desktop",
        executor_endpoint_id=MANAGER_ENDPOINT_MANAGED,
    )
    store.update_session(attached["session_id"], status="ready")

    binding = manager_channel_binding({}, session=manager_channel_session(store))

    assert binding["session_mode"] == "attached_host"
    assert binding["session_status"] == "ready"
    # The readback quotes the Session, and a public projection still carries no
    # host session id.
    assert "fixture-attached-host-session" not in json.dumps(binding)


def test_the_live_capabilities_readback_carries_the_channel_mode(tmp_path):
    """A frontend reads the mode from the channel it talks to, not from a guess."""

    store = ChatSessionStore(tmp_path / "runtime")
    session = store.create_session(
        goal_id="loopx-manager",
        agent_id="codex",
        adapter_kind="codex",
        upstream_thread_id="fixture-live-host-session",
        channel_id="manager",
        session_mode="attached_host",
        host_surface="desktop",
    )
    store.update_session(session["session_id"], status="busy")

    class Controller:
        def capabilities(self) -> list[dict[str, object]]:
            return []

        def close(self) -> None:
            return None

    server = ChatHTTPServer(("127.0.0.1", 0), ChatRequestHandler)
    server.verbose = False
    server.chat_store = store
    server.runtime_controller = Controller()
    server.lark_cli_resolution = LarkCliResolution(
        command=None,
        available=False,
        source="missing",
        version=None,
        error_code="lark_cli_not_installed",
    )
    server.selected_goal_id = ""
    server.scan_roots = []
    server.limit = 20
    server.registry_path = tmp_path / "registry.json"
    server.runtime_root_override = None
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f"http://127.0.0.1:{server.server_port}"

    try:
        with urllib.request.urlopen(f"{origin}/api/chat/capabilities") as response:
            payload = json.load(response)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()

    binding = payload["manager"]["channel_binding"]
    assert binding["session_mode"] == "attached_host"
    assert binding["session_status"] == "busy"
    assert binding["session_mode_source"] == (
        MANAGER_CHANNEL_SESSION_MODE_SOURCE_READBACK
    )
