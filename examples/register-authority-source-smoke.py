#!/usr/bin/env python3
"""Smoke-test redacted local authority-source registration."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "authority-source-registration-goal"
SOURCE_ID = "product-vision"
SOURCE_REF = "https://example.invalid/private/product-vision"
DOC = REPO_ROOT / "docs" / "authority-source-registration.md"


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = ".codex/goals/authority-source-registration-goal/ACTIVE_GOAL_STATE.md"
    registry = project / ".loopx" / "registry.json"
    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Authority Source Registration Goal\n",
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
                        "domain": "authority-source-registration",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "requires_authority_registry": True,
                        "authority_sources": [],
                        "authority_registry": {
                            "path": "docs/meta/DOC_REGISTRY.yaml",
                            "read_status": "not_read",
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
    return registry, runtime, project


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


def registration_args(*, dry_run: bool = False) -> list[str]:
    args = [
        "register-authority-source",
        "--goal-id",
        GOAL_ID,
        "--source-id",
        SOURCE_ID,
        "--source-ref",
        SOURCE_REF,
        "--source-kind",
        "doc",
        "--role",
        "current_authority",
        "--freshness",
        "owner_review_required",
        "--owner-status",
        "owner_review_pending",
        "--gate-status",
        "readable",
        "--boundary",
        "private_redacted",
        "--revision",
        "rev-2026-06-07",
        "--conflict-rule",
        "newer owner-approved source wins",
        "--topic",
        "product_vision",
    ]
    if dry_run:
        args.append("--dry-run")
    return args


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    for marker in (
        "register-authority-source",
        "authority_source_registration_v0",
        "source_ref_sha256",
        "source_ref_redacted=true",
        "private_redacted",
        "--no-global-sync",
        "Do not read or summarize the source body",
    ):
        assert marker in text, marker


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-authority-source-") as raw_tmp:
        registry, runtime, _project = write_fixture(Path(raw_tmp))
        before = registry.read_text(encoding="utf-8")
        dry = run_cli(registry, runtime, *registration_args(dry_run=True))
        assert dry["ok"] is True, dry
        assert dry["dry_run"] is True, dry
        assert dry["written"] is False, dry
        assert dry["entry"]["source_ref_redacted"] is True, dry
        assert dry["entry"]["source_ref_kind"] == "url", dry
        assert dry["entry"]["source_ref_sha256"] == hashlib.sha256(SOURCE_REF.encode("utf-8")).hexdigest(), dry
        assert registry.read_text(encoding="utf-8") == before, "dry-run must not mutate registry"

        written = run_cli(registry, runtime, *registration_args())
        assert written["ok"] is True, written
        assert written["written"] is True, written
        assert written["global_sync"]["wrote"] is True, written

        registry_text = registry.read_text(encoding="utf-8")
        assert SOURCE_REF not in registry_text, registry_text
        payload = json.loads(registry_text)
        goal = payload["goals"][0]
        material = goal["authority_registry"]["project_materials"][SOURCE_ID]
        assert material["schema_version"] == "authority_source_registration_v0", material
        assert material["role"] == "current_authority", material
        assert material["freshness"] == "owner_review_required", material
        assert material["source_ref_redacted"] is True, material
        assert "source_ref" not in material, material
        assert goal["authority_registry"]["topic_authority"]["product_vision"] == SOURCE_ID, goal
        assert goal["authority_sources"][0]["id"] == SOURCE_ID, goal["authority_sources"]

        global_path = Path(written["global_sync"]["global_registry"])
        global_payload = json.loads(global_path.read_text(encoding="utf-8"))
        global_goal = global_payload["goals"][0]
        assert "authority_sources" not in global_goal, global_goal
        assert SOURCE_REF not in global_path.read_text(encoding="utf-8"), global_path
        summary = global_goal["authority_registry"]
        assert summary["declared"] is True, summary
        assert summary["project_material_count"] == 1, summary
        assert summary["project_material_owner_review_required_count"] == 1, summary
        assert summary["project_material_current_authority_count"] == 1, summary

    assert_doc_contract()
    print("register-authority-source-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
