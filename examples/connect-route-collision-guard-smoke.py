#!/usr/bin/env python3
"""Smoke-test global route collision protection for connect/sync paths."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "loopx-meta-fixture"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def goal_entry(project: Path, registry_path: Path, *, agents: list[str] | None = None) -> dict:
    coordination = {
        "write_scope": [],
        "claim_ttl_minutes": 30,
        "requires_parent_approval": ["write", "publish", "production-action"],
    }
    if agents is not None:
        coordination["registered_agents"] = agents
        coordination["primary_agent"] = agents[0]
    return {
        "id": GOAL_ID,
        "domain": "collision-smoke",
        "status": "active",
        "repo": str(project),
        "state_file": ".codex/goals/loopx-meta-fixture/ACTIVE_GOAL_STATE.md",
        "adapter": {"kind": "fixture", "status": "connected-read-only"},
        "coordination": coordination,
        "source_registry": str(registry_path),
    }


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    runtime = root / "runtime"
    source_project = root / "source"
    intruder_project = root / "intruder"
    source_registry = source_project / ".loopx" / "registry.json"
    intruder_registry = intruder_project / ".loopx" / "registry.json"

    for project in (source_project, intruder_project):
        state = project / ".codex/goals/loopx-meta-fixture/ACTIVE_GOAL_STATE.md"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("# Active Goal State\n\n## Agent Todo\n\n", encoding="utf-8")

    source_payload = {
        "schema_version": "0.1",
        "common_runtime_root": str(runtime),
        "goals": [goal_entry(source_project, source_registry, agents=["codex-main-control"])],
    }
    intruder_payload = {
        "schema_version": "0.1",
        "common_runtime_root": str(runtime),
        "goals": [goal_entry(intruder_project, intruder_registry)],
    }
    write_json(source_registry, source_payload)
    write_json(intruder_registry, intruder_payload)
    global_payload = {
        "schema_version": "0.1",
        "common_runtime_root": str(runtime),
        "registry_role": "global-local",
        "goals": [goal_entry(source_project, source_registry, agents=["codex-main-control"])],
    }
    write_json(runtime / "registry.global.json", global_payload)
    return runtime, source_registry, intruder_registry, runtime / "registry.global.json"


def run_cli(registry: Path | None, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "loopx.cli", "--format", "json"]
    if registry is not None:
        command.extend(["--registry", str(registry)])
    command.extend(args)
    return subprocess.run(command, cwd=REPO_ROOT, check=check, text=True, capture_output=True)


def payload(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def only_goal(registry_path: Path) -> dict:
    return json.loads(registry_path.read_text(encoding="utf-8"))["goals"][0]


def assert_sync_collision_guard(root: Path) -> None:
    _, source_registry, intruder_registry, global_registry = write_fixture(root)
    original_global = global_registry.read_text(encoding="utf-8")

    blocked = payload(
        run_cli(intruder_registry, "sync-global", "--goal-id", GOAL_ID, check=False)
    )
    assert blocked["ok"] is False, blocked
    assert "global route collision" in blocked["error"], blocked
    assert global_registry.read_text(encoding="utf-8") == original_global

    dry_replace = payload(
        run_cli(
            intruder_registry,
            "sync-global",
            "--goal-id",
            GOAL_ID,
            "--replace-state",
            "--dry-run",
        )
    )
    assert dry_replace["ok"] is True, dry_replace
    assert dry_replace["route_replacement_allowed"] is True, dry_replace
    assert dry_replace["route_collisions"], dry_replace
    assert global_registry.read_text(encoding="utf-8") == original_global

    replaced = payload(
        run_cli(
            intruder_registry,
            "sync-global",
            "--goal-id",
            GOAL_ID,
            "--replace-state",
        )
    )
    assert replaced["ok"] is True, replaced
    assert replaced["backup_path"], replaced
    assert Path(replaced["backup_path"]).exists(), replaced
    assert Path(only_goal(global_registry)["source_registry"]).resolve() == intruder_registry.resolve()
    assert Path(only_goal(Path(replaced["backup_path"]))["source_registry"]).resolve() == source_registry.resolve()


def assert_register_agent_uses_source_registry(root: Path) -> None:
    runtime, source_registry, _intruder_registry, global_registry = write_fixture(root)

    preview = payload(
        run_cli(
            None,
            "--runtime-root",
            str(runtime),
            "register-agent",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            "codex-product-capability",
        )
    )
    assert preview["ok"] is True, preview
    assert preview["dry_run"] is True, preview
    assert preview["source_registry"] == str(source_registry), preview
    assert only_goal(source_registry)["coordination"]["registered_agents"] == ["codex-main-control"]

    applied = payload(
        run_cli(
            None,
            "--runtime-root",
            str(runtime),
            "register-agent",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            "codex-product-capability",
            "--execute",
        )
    )
    assert applied["ok"] is True, applied
    assert applied["written"] is True, applied
    source_agents = only_goal(source_registry)["coordination"]["registered_agents"]
    assert source_agents == ["codex-main-control", "codex-product-capability"], source_agents
    global_agents = only_goal(global_registry)["coordination"]["registered_agents"]
    assert global_agents == source_agents, global_agents
    assert Path(only_goal(global_registry)["source_registry"]).resolve() == source_registry.resolve()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-connect-route-collision-") as tmp:
        root = Path(tmp)
        assert_sync_collision_guard(root / "collision")
        assert_register_agent_uses_source_registry(root / "register-agent")
    print("connect-route-collision-guard-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
