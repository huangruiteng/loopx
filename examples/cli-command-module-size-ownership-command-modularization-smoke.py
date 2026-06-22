#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_COMMANDS = ROOT / "loopx" / "cli_commands"

DEFAULT_MAX_LINES = 500
LEGACY_MODULE_LIMITS = {
    "agents_last_exam.py": 700,
    "benchmark_review_lifecycle.py": 1300,
    "benchmark_run_ledger.py": 1360,
    "history.py": 720,
    "registry_admin.py": 780,
    "terminal_bench_adapter.py": 760,
    "terminal_bench_environment_result.py": 1280,
    "worker_bridge.py": 700,
}
STARTER_MODULE_LIMITS = {
    "starter.py": 160,
    "starter_bootstrap.py": 240,
    "starter_runtime_idle.py": 160,
    "starter_scheduler.py": 240,
    "starter_session_runtime.py": 220,
    "starter_visible_common.py": 120,
    "starter_visible_driver.py": 220,
    "starter_visible_pilot.py": 340,
}
STARTER_COMMAND_OWNERS = {
    "new-project-prompt": "starter_bootstrap.py",
    "codex-cli-bootstrap-message": "starter_bootstrap.py",
    "codex-cli-tui-bootstrap-smoke-bundle": "starter_bootstrap.py",
    "codex-cli-exec-handoff": "starter_bootstrap.py",
    "codex-cli-one-message-loop-pilot": "starter_visible_pilot.py",
    "codex-cli-visible-local-driver-pilot": "starter_visible_pilot.py",
    "codex-cli-bounded-visible-pilot-adapter": "starter_visible_pilot.py",
    "codex-cli-visible-first-response-capture-plan": "starter_visible_pilot.py",
    "codex-cli-visible-attach-acceptance": "starter_visible_pilot.py",
    "codex-cli-visible-driver-plan": "starter_visible_driver.py",
    "codex-cli-local-driver-plan": "starter_visible_driver.py",
    "codex-cli-visible-driver-run": "starter_visible_driver.py",
    "codex-cli-session-probe": "starter_session_runtime.py",
    "codex-cli-visible-session-proof": "starter_session_runtime.py",
    "codex-cli-runtime-idle-detector": "starter_session_runtime.py",
    "codex-cli-local-scheduler-tick": "starter_scheduler.py",
    "codex-cli-local-scheduler-exec": "starter_scheduler.py",
}

ADD_PARSER_RE = re.compile(
    r"\.add_parser\(\s*(?:\n\s*)?[\"'](?P<command>[^\"']+)[\"']",
    re.MULTILINE,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def python_modules() -> list[Path]:
    return sorted(path for path in CLI_COMMANDS.glob("*.py") if path.is_file())


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def line_count(path: Path) -> int:
    return len(source(path).splitlines())


def module_limit(module_name: str) -> int:
    if module_name in STARTER_MODULE_LIMITS:
        return STARTER_MODULE_LIMITS[module_name]
    return LEGACY_MODULE_LIMITS.get(module_name, DEFAULT_MAX_LINES)


def assert_module_size_budgets() -> None:
    module_names = {path.name for path in python_modules()}
    expected_budgets = set(STARTER_MODULE_LIMITS) | set(LEGACY_MODULE_LIMITS)
    stale_budgets = sorted(expected_budgets - module_names)
    require(not stale_budgets, f"size budgets reference missing modules: {stale_budgets}")

    for path in python_modules():
        count = line_count(path)
        limit = module_limit(path.name)
        require(
            count <= limit,
            f"{path.name} has {count} lines, above budget {limit}; "
            "split the command family before adding more code",
        )

    for module_name in sorted(LEGACY_MODULE_LIMITS):
        path = CLI_COMMANDS / module_name
        count = line_count(path)
        require(
            count > DEFAULT_MAX_LINES,
            f"{module_name} is down to {count} lines; remove its legacy size budget",
        )


def command_registrations() -> dict[str, list[str]]:
    registrations: dict[str, list[str]] = {}
    for path in python_modules():
        for match in ADD_PARSER_RE.finditer(source(path)):
            registrations.setdefault(match.group("command"), []).append(path.name)
    return registrations


def assert_command_registration_ownership() -> None:
    registrations = command_registrations()
    require(registrations, "expected at least one CLI add_parser registration")

    duplicate_registrations = {
        command: sorted(set(modules))
        for command, modules in registrations.items()
        if len(set(modules)) > 1
    }
    require(
        not duplicate_registrations,
        f"commands registered by multiple cli_commands modules: {duplicate_registrations}",
    )

    for command, expected_module in sorted(STARTER_COMMAND_OWNERS.items()):
        actual_modules = sorted(set(registrations.get(command, [])))
        require(
            actual_modules == [expected_module],
            f"{command} registration owner is {actual_modules}, expected {[expected_module]}",
        )


def main() -> None:
    assert_module_size_budgets()
    assert_command_registration_ownership()
    print("cli-command-module-size-ownership-command-modularization-smoke: ok")


if __name__ == "__main__":
    main()
