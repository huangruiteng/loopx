#!/usr/bin/env python3
"""Smoke-test planned read-only map opt-in handling."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "planned-main-control"


def write_planned_registry(root: Path) -> Path:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / "README.md").write_text("# Planned Project\n", encoding="utf-8")
    (project / "docs" / "meta").mkdir(parents=True, exist_ok=True)
    (project / "docs" / "TODO.md").write_text("# TODO\n", encoding="utf-8")
    (project / "docs" / "meta" / "DOC_REGISTRY.yaml").write_text("topics: {}\n", encoding="utf-8")
    (project / state_file).write_text(
        "---\n"
        "status: planned-high-complexity\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Planned Main Control\n\n"
        "## Authority Sources\n\n- README\n\n"
        "## Operating Contract\n\n- Read-only.\n\n"
        "## Work Clusters\n\n- Map first.\n\n"
        "## Validation Surfaces\n\n- Smoke.\n\n"
        "## Private/Public Boundary\n\n- Public-safe only.\n\n"
        "## Next Action\n\n- Wait for controller opt-in.\n\n"
        "## Progress Ledger\n\n- Connected.\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "complex-project",
                        "status": "planned-high-complexity",
                        "repo": str(project),
                        "state_file": state_file,
                        "authority_sources": [{"kind": "doc", "role": "primary", "path": "README.md"}],
                        "authority_registry": {
                            "declared": True,
                            "required": True,
                            "path": "docs/meta/DOC_REGISTRY.yaml",
                            "path_exists": False,
                            "read_status": "read",
                            "default_entry_count": 99,
                            "default_entries_checked": 99,
                            "default_entries_present": 99,
                            "topic_authority_count": 99,
                            "project_material_count": 99,
                            "default_entry_docs": [
                                "docs/TODO.md",
                                "docs/meta/DOC_REGISTRY.yaml",
                            ],
                            "topic_authority": {
                                "current_priority": "docs/TODO.md",
                            },
                            "project_materials": {
                                "migration_design": {
                                    "role": "current_authority",
                                    "source_kind": "external_doc",
                                    "freshness": "owner_review_required",
                                },
                                "source_repo": {
                                    "role": "source_surface",
                                    "source_kind": "repository",
                                    "freshness": "read_only_status_ok",
                                },
                                "target_repo": {
                                    "role": "implementation_surface",
                                    "source_kind": "repository",
                                    "freshness": "read_only_status_ok",
                                },
                                "historical_note": {
                                    "role": "historical_reference",
                                    "source_kind": "external_doc",
                                    "freshness": "stale",
                                },
                            },
                            "deprecated_source_count": 0,
                            "conflict_risk": "low",
                        },
                        "adapter": {
                            "kind": "complex_project_read_only_map_v0",
                            "status": "planned",
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return registry_path


def run_cli(root: Path, registry_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(root / "runtime"),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-project-map-") as tmp:
        root = Path(tmp)
        registry_path = write_planned_registry(root)
        before = json.loads(
            run_cli(root, registry_path, "read-only-map", "--goal-id", GOAL_ID, "--dry-run").stdout
        )
        assert before["ok"] is True, before
        assert before["dry_run"] is True, before
        assert before["opt_in_required"] is True, before
        assert "planned_adapter_requires_controller_opt_in" in before["residual_risks"], before

        local_action = "/Users/example/private/project-next-action"
        local_gate = json.loads(
            run_cli(
                root,
                registry_path,
                "operator-gate",
                "--goal-id",
                GOAL_ID,
                "--decision",
                "defer",
                "--reason-summary",
                "暂缓，只测试 local-control routing text.",
                "--recommended-action",
                local_action,
                "--dry-run",
            ).stdout
        )
        assert local_gate["recommended_action"] == local_action, local_gate

        secret_action = "Continue with access_" + "key=" + "AKIA" + "1234567890ABCDEF"
        secret_gate = run_cli(
            root,
            registry_path,
            "operator-gate",
            "--goal-id",
            GOAL_ID,
            "--decision",
            "defer",
            "--reason-summary",
            "暂缓，只测试敏感值拦截.",
            "--recommended-action",
            secret_action,
            "--dry-run",
            check=False,
        )
        assert secret_gate.returncode != 0, secret_gate.stdout
        assert "recommended_action contains a secret-looking value" in secret_gate.stdout, secret_gate.stdout

        run_cli(
            root,
            registry_path,
            "operator-gate",
            "--goal-id",
            GOAL_ID,
            "--decision",
            "approve",
            "--reason-summary",
            "同意 planned-main-control 先做 read-only map dry-run，不授权写入或主控接管",
        )
        after = json.loads(
            run_cli(root, registry_path, "read-only-map", "--goal-id", GOAL_ID, "--dry-run").stdout
        )
        assert after["ok"] is True, after
        assert after["dry_run"] is True, after
        assert after["appended"] is False, after
        assert after["opt_in_required"] is False, after
        assert after["operator_gate"]["decision"] == "approve", after
        assert "planned_adapter_requires_controller_opt_in" not in after["residual_risks"], after
        assert "do not append real run history or grant write-control" in after["recommended_action"], after
        project_map = after["project_map"]
        assert project_map["authority_registry_path_exists"] is True, project_map
        assert project_map["authority_registry_default_entry_count"] == 2, project_map
        assert project_map["authority_registry_default_entries_present"] == 2, project_map
        assert project_map["topic_authority_count"] == 1, project_map
        assert project_map["project_material_count"] == 4, project_map
        assert project_map["project_material_repository_count"] == 2, project_map
        assert project_map["project_material_owner_review_required_count"] == 1, project_map
        assert project_map["project_material_stale_count"] == 1, project_map
        assert project_map["project_material_current_authority_count"] == 1, project_map

        local_map = json.loads(
            run_cli(
                root,
                registry_path,
                "read-only-map",
                "--goal-id",
                GOAL_ID,
                "--recommended-action",
                local_action,
                "--dry-run",
            ).stdout
        )
        assert local_map["recommended_action"] == local_action, local_map
        secret_map = run_cli(
            root,
            registry_path,
            "read-only-map",
            "--goal-id",
            GOAL_ID,
            "--recommended-action",
            secret_action,
            "--dry-run",
            check=False,
        )
        assert secret_map.returncode != 0, secret_map.stdout
        assert "recommended_action contains a secret-looking value" in secret_map.stdout, secret_map.stdout

        real_map = run_cli(root, registry_path, "read-only-map", "--goal-id", GOAL_ID, check=False)
        assert real_map.returncode != 0, real_map.stdout
        assert "planned adapters may only run read-only-map with --dry-run" in real_map.stdout, real_map.stdout

    print("project-map-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
