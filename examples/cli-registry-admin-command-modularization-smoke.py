#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "loopx" / "cli.py"
MODULE = ROOT / "loopx" / "cli_commands" / "registry_admin.py"
AUTHORITY_MODULE = ROOT / "loopx" / "cli_commands" / "registry_authority.py"
INIT = ROOT / "loopx" / "cli_commands" / "__init__.py"
GOAL_ID = "registry-admin-smoke"

def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_success(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode != 0:
        raise AssertionError(
            f"expected success, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return result.stdout


def require_json_success(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    stdout = require_success(result)
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"expected JSON output, got:\n{stdout}") from exc
    require(payload.get("ok") is True, f"payload was not ok: {payload}")
    return payload


def run_json(command_prefix: tuple[str, ...], command: str, *args: str) -> dict[str, object]:
    return require_json_success(run_cli(*command_prefix, command, *args))

def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_fixture(project: Path) -> tuple[Path, Path, Path, Path]:
    runtime_root = project / "runtime"
    registry_path = project / ".loopx" / "registry.json"
    legacy_registry_path = project / "legacy" / "registry.global.json"
    doc_registry_path = project / "DOC_REGISTRY.yaml"
    obsolete_runtime = runtime_root / "goals" / "obsolete-runtime-goal" / "runs"
    obsolete_runtime.mkdir(parents=True, exist_ok=True)
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("# Registry Admin Smoke State\n", encoding="utf-8")
    (project / "README.md").write_text("# Registry Admin Smoke\n", encoding="utf-8")

    goal = {
        "id": GOAL_ID,
        "objective": "Validate registry admin command modularization.",
        "domain": "smoke",
        "repo": str(project),
        "state_file": ".codex/goals/registry-admin-smoke/ACTIVE_GOAL_STATE.md",
        "status": "connected-read-only",
        "adapter": {"kind": "read_only_project_map_v0", "status": "connected-read-only"},
        "coordination": {
            "registered_agents": [{"id": "codex-main-control", "role": "primary"}],
            "primary_agent": "codex-main-control",
        },
        "guards": ["dry-run registry admin smoke fixture only"],
    }
    registry_payload = {
        "schema_version": "0.1",
        "registry_role": "project-local",
        "common_runtime_root": str(runtime_root),
        "goals": [goal],
    }
    write_json(registry_path, registry_payload)
    write_json(
        runtime_root / "registry.global.json",
        {
            "schema_version": "0.1",
            "registry_role": "global-local",
            "common_runtime_root": str(runtime_root),
            "goals": [{**goal, "source_registry": str(registry_path)}],
        },
    )
    write_json(
        legacy_registry_path,
        {
            "schema_version": "0.1",
            "common_runtime_root": str(project / "legacy-runtime"),
            "goals": [
                {
                    "id": "legacy-smoke-goal",
                    "objective": "Legacy smoke goal.",
                    "repo": str(project / "legacy-repo"),
                    "state_file": ".codex/goals/legacy-smoke-goal/ACTIVE_GOAL_STATE.md",
                    "status": "legacy",
                }
            ],
        },
    )
    doc_registry_path.write_text(
        "version: doc_registry_v0\n"
        "updated_at: 2026-06-22T00:00:00+00:00\n"
        "default_entry_docs:\n"
        "  - README.md\n"
        "topic_authority:\n"
        "  issue_fix: README.md\n"
        "status_definitions:\n"
        "  current: usable\n",
        encoding="utf-8",
    )
    return registry_path, runtime_root, legacy_registry_path, doc_registry_path


def main() -> None:
    cli_source = CLI.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    authority_source = AUTHORITY_MODULE.read_text(encoding="utf-8")
    registry_admin_family_source = module_source + "\n" + authority_source
    init_source = INIT.read_text(encoding="utf-8")

    forbidden_cli_markers = [
        "configure_goal_parser = sub.add_parser",
        "register_agent_parser = sub.add_parser",
        "archive_runtime_parser = sub.add_parser",
        "sync_global_parser = sub.add_parser",
        "migrate_state_parser = sub.add_parser",
        "authority_parser = sub.add_parser",
        "doc_registry_authority_parser = sub.add_parser",
        "register_agent_via_source_registry(",
        "configure_goal(",
        "archive_runtime_goal(",
        "migrate_legacy_state(",
        "register_authority_source(",
        "import_doc_registry_authority(",
        'if args.command == "configure-goal":',
        'if args.command == "register-agent":',
        'if args.command == "archive-runtime":',
        'if args.command == "uninstall-project":',
        'if args.command == "sync-global":',
        'if args.command == "migrate-state":',
        'if args.command == "register-authority-source":',
        'if args.command == "import-doc-registry-authority":',
    ]
    for marker in forbidden_cli_markers:
        require(marker not in cli_source, f"registry admin marker leaked into cli.py: {marker}")

    for marker in (
        "REGISTRY_ADMIN_COMMANDS",
        "register_registry_admin_commands",
        "handle_registry_admin_command",
        "configure-goal",
        "register-agent",
        "archive-runtime",
        "uninstall-project",
        "sync-global",
        "migrate-state",
        "register-authority-source",
        "import-doc-registry-authority",
    ):
        require(marker in registry_admin_family_source, f"registry admin command family missing {marker}")
    for marker in (
        "REGISTRY_AUTHORITY_COMMANDS",
        "register_registry_authority_commands",
        "handle_registry_authority_command",
        'if args.command == "register-authority-source":',
        'if args.command != "import-doc-registry-authority":',
        "register_authority_source(",
        "import_doc_registry_authority(",
    ):
        require(marker in authority_source, f"registry authority module missing {marker}")
    for marker in ("register_registry_authority_commands", "handle_registry_authority_command"):
        require(marker in module_source, f"registry admin module should delegate authority commands through {marker}")
    require("register_registry_admin_commands" in cli_source, "cli.py did not register registry admin commands")
    require("handle_registry_admin_command" in cli_source, "cli.py did not dispatch registry admin commands")
    require("register_registry_admin_commands" in init_source, "__init__ did not export registry admin registration")
    require("handle_registry_admin_command" in init_source, "__init__ did not export registry admin handler")

    for command, options in {
        "configure-goal": ("--quota-compute", "--registered-agent", "--execute"),
        "register-agent": ("--agent-id", "--primary-agent", "--execute"),
        "archive-runtime": ("--archive-root", "--allow-registered", "--execute"),
        "uninstall-project": ("--goal-id", "--archive-state", "--remove-empty-registry", "--execute"),
        "sync-global": ("--replace-state", "--dry-run"),
        "migrate-state": ("--legacy-registry", "--goal-id-map", "--copy-runtime"),
        "register-authority-source": ("--source-ref", "--boundary", "--no-global-sync"),
        "import-doc-registry-authority": ("--doc-registry-path", "--import-topic-prefix", "--max-imported-topics"),
    }.items():
        help_text = require_success(run_cli(command, "--help"))
        for option in options:
            require(option in help_text, f"{command} help omitted {option}")

    with tempfile.TemporaryDirectory(prefix="loopx-registry-admin-cli-") as tmp:
        project = Path(tmp)
        registry_path, runtime_root, legacy_registry_path, doc_registry_path = write_fixture(project)
        command_prefix = ("--format", "json", "--registry", str(registry_path), "--runtime-root", str(runtime_root))
        registry_before = registry_path.read_text(encoding="utf-8")

        configure_payload = run_json(
            command_prefix,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "2",
            "--registered-agent",
            "codex-product-capability",
        )
        require(configure_payload.get("dry_run") is True, "configure-goal should preview by default")
        require(configure_payload.get("written") is False, "configure-goal preview should not write")

        register_payload = run_json(
            command_prefix,
            "register-agent",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            "codex-product-capability",
        )
        require(register_payload.get("dry_run") is True, "register-agent should preview by default")
        require("codex-product-capability" in (register_payload.get("registered_agents") or []), register_payload)

        archive_payload = run_json(command_prefix, "archive-runtime", "--goal-id", "obsolete-runtime-goal")
        require(archive_payload.get("dry_run") is True, "archive-runtime should dry-run by default")
        require(archive_payload.get("archived") is False, "archive-runtime preview should not move")
        require((runtime_root / "goals" / "obsolete-runtime-goal").exists(), "archive-runtime preview moved source")

        uninstall_payload = run_json(command_prefix, "uninstall-project", "--goal-id", GOAL_ID, "--archive-state")
        require(uninstall_payload.get("dry_run") is True, "uninstall-project should dry-run by default")
        require(uninstall_payload.get("wrote_local_registry") is False, "uninstall-project preview should not write local registry")
        require(uninstall_payload.get("wrote_global_registry") is False, "uninstall-project preview should not write global registry")
        require(registry_path.read_text(encoding="utf-8") == registry_before, "uninstall-project preview changed registry")

        sync_payload = run_json(command_prefix, "sync-global", "--goal-id", GOAL_ID, "--dry-run")
        require(sync_payload.get("dry_run") is True, "sync-global should honor --dry-run")
        require(sync_payload.get("wrote") is False, "sync-global dry-run should not write")

        migrate_payload = run_json(
            command_prefix,
            "migrate-state",
            "--legacy-registry",
            str(legacy_registry_path),
            "--legacy-runtime-root",
            str(project / "legacy-runtime"),
            "--target-runtime-root",
            str(runtime_root),
            "--goal-id",
            "legacy-smoke-goal",
            "--goal-id-map",
            "legacy-smoke-goal=migrated-smoke-goal",
            "--no-global-sync",
        )
        require(migrate_payload.get("dry_run") is True, "migrate-state should dry-run by default")
        require(migrate_payload.get("wrote_project_registry") is False, "migrate-state preview should not write")
        require("migrated-smoke-goal" in (migrate_payload.get("migrated_goal_ids") or []), migrate_payload)

        authority_payload = run_json(
            command_prefix,
            "register-authority-source",
            "--goal-id",
            GOAL_ID,
            "--source-id",
            "source-smoke",
            "--source-ref",
            "https://example.com/public-smoke",
            "--source-kind",
            "doc",
            "--role",
            "smoke_authority",
            "--freshness",
            "current",
            "--topic",
            "issue_fix",
            "--dry-run",
            "--no-global-sync",
        )
        require(authority_payload.get("dry_run") is True, "authority registration should honor --dry-run")
        require(authority_payload.get("written") is False, "authority dry-run should not write")
        require(authority_payload.get("raw_source_ref_stored") is False, "authority source ref must stay redacted")

        doc_payload = run_json(
            command_prefix,
            "import-doc-registry-authority",
            "--goal-id",
            GOAL_ID,
            "--source-id",
            "doc-registry-smoke",
            "--doc-registry-path",
            str(doc_registry_path),
            "--topic",
            "content_ops",
            "--import-topic-prefix",
            "smoke:",
            "--dry-run",
            "--no-global-sync",
        )
        require(doc_payload.get("dry_run") is True, "doc registry import should honor --dry-run")
        require(doc_payload.get("written") is False, "doc registry import dry-run should not write")
        require(doc_payload.get("raw_doc_registry_path_stored") is False, "doc registry path must stay redacted")
        require(registry_path.read_text(encoding="utf-8") == registry_before, "dry-run commands mutated registry")

    print("cli-registry-admin-command-modularization-smoke: ok")


if __name__ == "__main__":
    main()
