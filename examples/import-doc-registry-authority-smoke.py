#!/usr/bin/env python3
"""Smoke-test importing a DOC_REGISTRY summary as authority context."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "doc-registry-authority-import-goal"
SOURCE_ID = "external-doc-registry"
DOC = REPO_ROOT / "docs" / "authority-source-registration.md"


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = ".codex/goals/doc-registry-authority-import-goal/ACTIVE_GOAL_STATE.md"
    registry = project / ".loopx" / "registry.json"
    doc_registry = project / "external" / "DOC_REGISTRY.yaml"
    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Doc Registry Authority Import Goal\n",
        encoding="utf-8",
    )
    doc_registry.parent.mkdir(parents=True, exist_ok=True)
    doc_registry.write_text(
        "version: 1\n"
        "updated_at: 2026-06-07\n"
        "purpose: >-\n"
        "  Fixture registry.\n"
        "status_definitions:\n"
        "  active: Current authority.\n"
        "  deprecated: Old authority.\n"
        "default_entry_docs:\n"
        "  - docs/TODO.md\n"
        "  - docs/meta/DOC_REGISTRY.yaml\n"
        "  - docs/SYSTEM_DESIGN.md\n"
        "topic_authority:\n"
        "  current_priority: docs/TODO.md\n"
        "  benchmark_landscape: docs/research/BENCHMARKS.md\n"
        "  codex_cli_usage: docs/research/CODEX_CLI.md\n",
        encoding="utf-8",
    )
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "doc-registry-authority-import",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "requires_authority_registry": True,
                        "authority_sources": [],
                        "authority_registry": {
                            "path": "docs/meta/DOC_REGISTRY.yaml",
                            "read_status": "not_read",
                            "topic_authority": {"existing_topic": "existing-source"},
                        },
                        "adapter": {
                            "kind": "fixture_connected_readonly_v0",
                            "status": "connected-read-only",
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry, runtime, project, doc_registry


def run_cli(registry: Path, runtime: Path, *args: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime),
            *args,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def import_args(doc_registry: Path, *, dry_run: bool = False) -> list[str]:
    args = [
        "import-doc-registry-authority",
        "--goal-id",
        GOAL_ID,
        "--source-id",
        SOURCE_ID,
        "--doc-registry-path",
        str(doc_registry),
        "--role",
        "external_doc_authority",
        "--freshness",
        "current",
        "--owner-status",
        "owner_review_not_required",
        "--gate-status",
        "readable",
        "--boundary",
        "private_redacted",
        "--conflict-rule",
        "imported registry informs external project context",
        "--topic",
        "external_doc_registry",
        "--import-topic-prefix",
        "external_",
        "--max-imported-topics",
        "2",
    ]
    if dry_run:
        args.append("--dry-run")
    return args


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    for marker in (
        "Project-Local Doc Registry Mechanism",
        "Doc registry is a general LoopX mechanism",
        "not an agent-harness-specific",
        "Identify the target project and goal first",
        "project's own doc registry",
        "Executor Skill Contract",
        "doc-registry skill trigger",
        "Run the relevant smoke or status refresh before spending heartbeat quota",
        "import-doc-registry-authority",
        "doc_registry_authority_import_v0",
        "default_entry_count",
        "topic_authority_count",
        "raw `DOC_REGISTRY.yaml` path is hashed",
    ):
        assert marker in text, marker


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-doc-registry-authority-") as raw_tmp:
        registry, runtime, _project, doc_registry = write_fixture(Path(raw_tmp))
        before = registry.read_text(encoding="utf-8")
        dry = run_cli(registry, runtime, *import_args(doc_registry, dry_run=True))
        assert dry["ok"] is True, dry
        assert dry["dry_run"] is True, dry
        assert dry["written"] is False, dry
        assert dry["entry"]["source_ref_sha256"] == hashlib.sha256(str(doc_registry).encode("utf-8")).hexdigest(), dry
        assert registry.read_text(encoding="utf-8") == before, "dry-run must not mutate registry"

        written = run_cli(registry, runtime, *import_args(doc_registry))
        assert written["ok"] is True, written
        assert written["written"] is True, written
        assert written["global_sync"]["wrote"] is True, written

        registry_text = registry.read_text(encoding="utf-8")
        assert str(doc_registry) not in registry_text, registry_text
        payload = json.loads(registry_text)
        goal = payload["goals"][0]
        material = goal["authority_registry"]["project_materials"][SOURCE_ID]
        assert material["schema_version"] == "doc_registry_authority_import_v0", material
        assert material["default_entry_count"] == 3, material
        assert material["topic_authority_count"] == 3, material
        assert material["status_definition_count"] == 2, material
        assert material["imported_topic_count"] == 3, material
        assert material["imported_topic_truncated"] is True, material
        topics = goal["authority_registry"]["topic_authority"]
        assert topics["existing_topic"] == "existing-source", topics
        assert topics["external_doc_registry"] == SOURCE_ID, topics
        assert topics["external_current_priority"] == SOURCE_ID, topics
        assert topics["external_benchmark_landscape"] == SOURCE_ID, topics
        assert "external_codex_cli_usage" not in topics, topics

        global_path = Path(written["global_sync"]["global_registry"])
        global_text = global_path.read_text(encoding="utf-8")
        assert str(doc_registry) not in global_text, global_text
        global_goal = json.loads(global_text)["goals"][0]
        assert "authority_sources" not in global_goal, global_goal
        summary = global_goal["authority_registry"]
        assert summary["project_material_count"] == 1, summary
        assert summary["project_material_current_authority_count"] == 1, summary
        assert summary["topic_authority_count"] == 4, summary

    assert_doc_contract()
    print("import-doc-registry-authority-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
