#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench managed Codex custom-agent bridge."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH,
    build_terminal_bench_benchmark_run,
    build_terminal_bench_managed_harbor_command,
)


TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-managed-codex-custom-agent-v0.md"
README = TOPIC_DIR / "README.md"

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench Managed Codex Custom Agent V0",
    "--agent-import-path",
    "loopx.terminal_bench_agent:GoalHarnessManagedCodex",
    "loopx_managed_codex",
    "loopx_terminal_bench_policy_v0",
    "terminal_bench_loopx_managed_codex_v0",
    "case_semantics_changed_by_harness",
    "official_score_comparable_to_native_codex",
    "model_plus_harness_pair",
    "context_metadata_deferred_until_post_run",
    "codex_cli_session_token_count_event",
    "Run exactly one private no-upload managed Codex single-task pilot",
    "python3 examples/terminal-bench-managed-codex-custom-agent-smoke.py",
]

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "DOUBAO" + "_MODEL=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
    "tok" + "en=",
    "-----BEGIN",
]


class FakeAgentContext:
    def __init__(self) -> None:
        self.n_input_tokens: int | None = None
        self.n_cache_tokens: int | None = None
        self.n_output_tokens: int | None = None
        self.cost_usd: float | None = None
        self.metadata: dict[str, Any] | None = None

    def is_empty(self) -> bool:
        return all(
            value is None
            for value in (
                self.n_input_tokens,
                self.n_cache_tokens,
                self.n_output_tokens,
                self.cost_usd,
                self.metadata,
            )
        )


class FakeCodex:
    SUPPORTS_ATIF = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.logs_dir = Path(kwargs.get("logs_dir") or (args[0] if args else "logs"))
        self.received_instruction: str | None = None
        self.exec_calls: list[dict[str, Any]] = []

    @staticmethod
    def name() -> str:
        return "codex"

    async def exec_as_root(
        self,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "root",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        return types.SimpleNamespace(return_code=0, stdout="", stderr="")

    async def exec_as_agent(
        self,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "agent",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        return types.SimpleNamespace(return_code=0, stdout="", stderr="")

    async def run(
        self,
        instruction: str,
        environment: object,
        context: FakeAgentContext,
    ) -> None:
        self.received_instruction = instruction

    def populate_context_post_run(self, context: FakeAgentContext) -> None:
        context.n_input_tokens = 123
        context.n_cache_tokens = 45
        context.n_output_tokens = 67
        context.cost_usd = 0.89


def install_fake_harbor_modules() -> None:
    modules = {
        "harbor": types.ModuleType("harbor"),
        "harbor.agents": types.ModuleType("harbor.agents"),
        "harbor.agents.installed": types.ModuleType("harbor.agents.installed"),
        "harbor.agents.installed.codex": types.ModuleType("harbor.agents.installed.codex"),
        "harbor.environments": types.ModuleType("harbor.environments"),
        "harbor.environments.base": types.ModuleType("harbor.environments.base"),
        "harbor.models": types.ModuleType("harbor.models"),
        "harbor.models.agent": types.ModuleType("harbor.models.agent"),
        "harbor.models.agent.context": types.ModuleType("harbor.models.agent.context"),
    }
    modules["harbor.agents.installed.codex"].Codex = FakeCodex
    modules["harbor.environments.base"].BaseEnvironment = object
    modules["harbor.models.agent.context"].AgentContext = FakeAgentContext
    sys.modules.update(modules)


def load_agent_module() -> Any:
    install_fake_harbor_modules()
    module_path = REPO_ROOT / "loopx" / "terminal_bench_agent.py"
    spec = importlib.util.spec_from_file_location("loopx_terminal_bench_agent_smoke", module_path)
    assert spec and spec.loader, module_path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 20000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert "terminal-bench-managed-codex-custom-agent-v0.md" in readme, readme


def assert_command_contract() -> None:
    command = build_terminal_bench_managed_harbor_command()
    joined = " ".join(command)
    assert "--agent-import-path" in command, command
    assert TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH in command, command
    assert "--agent-kwarg" in command, command
    assert "terminal-bench@2.0" in command, command
    assert "build-cython-ext" in command, command
    assert "--upload" not in command, command
    assert "--public" not in command, command
    assert "--share-org" not in command, command
    assert "<private-jobs-dir>" in command, command
    assert_public_safe(joined)

    event = build_terminal_bench_benchmark_run(mode="loopx-managed-codex")
    assert event["agent"]["import_path"] == TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH, event
    assert event["managed_runner_command_preview"] == command, event
    assert event["real_run"] is False, event
    assert event["submit_eligible"] is False, event
    assert event["model_plus_harness_pair"] is True, event
    assert_public_safe(event)


def assert_adapter_contract() -> None:
    module = load_agent_module()
    task = "Build the extension and make the test pass."
    managed = module.build_managed_terminal_bench_instruction(task)
    assert "LoopX managed Codex mode" in managed, managed
    assert "----- TERMINAL-BENCH TASK -----" in managed, managed
    assert module.TERMINAL_BENCH_CASE_STATE_PATH in managed, managed
    assert module.BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION in managed, managed
    assert task in managed, managed

    agent = module.GoalHarnessManagedCodex(logs_dir=Path("logs"), model_name="gpt-5.5")
    assert agent.name() == "loopx-managed-codex", agent.name()
    context = FakeAgentContext()
    asyncio.run(agent.run(task, object(), context))
    assert agent.received_instruction is not None
    assert "LoopX managed Codex mode" in agent.received_instruction
    assert module.TERMINAL_BENCH_CASE_STATE_PATH in agent.received_instruction
    assert task in agent.received_instruction
    root_calls = [call for call in agent.exec_calls if call["user"] == "root"]
    assert len(root_calls) == 1, root_calls
    init_command = root_calls[0]["command"]
    assert "/app/.codex/goals/terminal-bench-case/ACTIVE_GOAL_STATE.md" in init_command
    assert ".loopx-case-state.md" not in init_command
    assert module.BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION in init_command
    assert context.is_empty(), context.metadata
    agent.populate_context_post_run(context)
    assert context.n_input_tokens == 123, context.n_input_tokens
    assert context.n_cache_tokens == 45, context.n_cache_tokens
    assert context.n_output_tokens == 67, context.n_output_tokens
    assert context.cost_usd == 0.89, context.cost_usd
    loopx = context.metadata["loopx"]
    assert loopx["mode"] == "loopx_managed_codex", loopx
    assert loopx["loopx_inside_case"] is True, loopx
    assert loopx["case_semantics_changed_by_harness"] is True, loopx
    assert loopx["official_score_comparable_to_native_codex"] is False, loopx
    assert loopx["model_plus_harness_pair"] is True, loopx
    assert loopx["raw_task_instruction_recorded"] is False, loopx
    assert loopx["raw_managed_prompt_recorded"] is False, loopx
    assert loopx["case_goal_state_init_required"] is True, loopx
    assert loopx["case_goal_state_initialized_before_agent"] is True, loopx
    assert loopx["case_goal_state_init_status"] == "passed", loopx
    assert (
        loopx["case_goal_state_schema_version"]
        == module.BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
    ), loopx
    assert (
        loopx["case_goal_state_path"]
        == module.TERMINAL_BENCH_CASE_STATE_PATH
    ), loopx
    counters = loopx["loopx_interaction_counters"]
    assert counters["case_goal_state_init_required"] is True, counters
    assert counters["case_goal_state_initialized_before_agent"] is True, counters
    assert counters["loopx_case_state_writes"] == 1, counters
    assert counters["case_goal_state_path"] == module.TERMINAL_BENCH_CASE_STATE_PATH
    assert loopx["leaderboard_evidence"] is False, loopx
    assert loopx["context_metadata_deferred_until_post_run"] is True, loopx
    assert loopx["context_post_run_ingested"] is True, loopx
    assert loopx["usage_source"] == "codex_cli_session_token_count_event", loopx
    assert loopx["token_cost_fallback_applied"] is False, loopx
    assert_public_safe(loopx)


def assert_session_usage_fallback_contract() -> None:
    module = load_agent_module()
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_dir = Path(tmp_dir)
        session_file = session_dir / "rollout.jsonl"
        session_file.write_text(
            "\n".join(
                [
                    json.dumps({"type": "response_item", "payload": {"type": "message"}}),
                    json.dumps(
                        {
                            "type": "event_msg",
                            "payload": {
                                "type": "token_count",
                                "info": {
                                    "total_token_usage": {
                                        "input_tokens": 100,
                                        "cached_input_tokens": 25,
                                        "output_tokens": 12,
                                        "reasoning_output_tokens": 3,
                                        "total_tokens": 112,
                                    }
                                },
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )
        usage = module.extract_codex_session_usage(session_dir)
    assert usage == {
        "input_tokens": 100,
        "cache_tokens": 25,
        "output_tokens": 12,
        "reasoning_output_tokens": 3,
        "total_tokens": 112,
    }, usage
    assert_public_safe(usage)


def main() -> int:
    assert_doc_contract()
    assert_command_contract()
    assert_adapter_contract()
    assert_session_usage_fallback_contract()
    print("ok: terminal bench managed codex custom agent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
