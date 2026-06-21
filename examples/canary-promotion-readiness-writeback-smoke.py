#!/usr/bin/env python3
"""Smoke-test canary promotion-readiness evidence writeback isolation.

The same temporary HOME/runtime is used by the readiness writeback and
`install-local.sh`, so this also verifies the installer promotion gate consumes
the event written by the canary readiness path.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-local.sh"
GOAL_ID = "loopx-meta"


def load_canary_smoke_module():
    path = REPO_ROOT / "examples" / "canary-promotion-readiness-smoke.py"
    spec = importlib.util.spec_from_file_location("canary_promotion_readiness_smoke", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_install(env: dict[str, str], release_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALL_SCRIPT)],
        cwd=REPO_ROOT,
        env={**env, "LOOPX_RELEASE_ID": release_id},
        check=True,
        capture_output=True,
        text=True,
    )


def run_promotion_gate(env: dict[str, str], runtime: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "promotion-gate",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def write_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    home = root / "home"
    project = root / "project"
    runtime = home / ".codex" / "loopx"
    state_file = f"goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    home.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active-read-only\n"
        "owner_mode: goal\n"
        'objective: "Exercise canary promotion readiness writeback."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Canary Promotion Writeback Fixture\n\n"
        "## Next Action\n\n"
        "- Keep promotion readiness evidence public-safe and ledger-backed.\n",
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
                        "domain": "loopx-meta",
                        "status": "active-read-only",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, runtime, state_path, home


def main() -> int:
    module = load_canary_smoke_module()
    with tempfile.TemporaryDirectory(prefix="loopx-canary-writeback-smoke-") as raw_tmp:
        root = Path(raw_tmp)
        registry_path, runtime, state_path, home = write_fixture(root)
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "LOOPX_BIN_DIR": str(home / ".local" / "bin"),
            "LOOPX_INSTALL_SKILL": "0",
            "LOOPX_RELEASES_DIR": str(root / "releases"),
            "LOOPX_SHELL_PROFILE": str(home / ".zshrc"),
            "LOOPX_REGISTRY": str(registry_path),
            "PYTHONPATH": str(REPO_ROOT),
            "SHELL": "/bin/zsh",
        }

        missing_gate = run_promotion_gate(env, runtime)
        assert missing_gate["ok"] is True, missing_gate
        assert missing_gate["gate"] == "promotion_readiness", missing_gate
        assert missing_gate["gate_state"] == "warning", missing_gate
        assert missing_gate["can_promote"] is False, missing_gate
        assert missing_gate["should_warn"] is True, missing_gate
        assert missing_gate["readiness"]["freshness_status"] == "missing", missing_gate
        assert "promotion-readiness evidence is missing" in missing_gate["warning_message"], missing_gate

        preflight_install = run_install(env, "before-readiness-evidence")
        assert "loopx installed locally" in preflight_install.stdout, preflight_install.stdout
        assert "promotion-readiness evidence is missing" in preflight_install.stderr, preflight_install.stderr
        assert "non-blocking" in preflight_install.stderr, preflight_install.stderr

        module.write_readiness_evidence(env)

        index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
        assert index_path.is_file(), index_path
        records = [
            json.loads(line)
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1, records
        record = records[0]
        assert record["classification"] == module.READINESS_CLASSIFICATION, record
        assert record["goal_id"] == GOAL_ID, record
        assert record["delivery_batch_scale"] == "multi_surface", record
        assert record["delivery_outcome"] == "primary_goal_outcome", record
        assert record["recommended_action"] == module.READINESS_RECOMMENDED_ACTION, record

        json_path = Path(record["json_path"])
        markdown_path = Path(record["markdown_path"])
        assert json_path.is_file(), json_path
        assert markdown_path.is_file(), markdown_path
        assert runtime in json_path.parents, json_path
        assert runtime in markdown_path.parents, markdown_path

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["classification"] == module.READINESS_CLASSIFICATION, payload
        assert payload["delivery_batch_scale"] == "multi_surface", payload
        assert payload["delivery_outcome"] == "primary_goal_outcome", payload
        assert payload["state"]["path"] == str(state_path), payload

        global_registry = runtime / "registry.global.json"
        assert global_registry.is_file(), global_registry
        global_payload = json.loads(global_registry.read_text(encoding="utf-8"))
        assert global_payload["common_runtime_root"] == str(runtime), global_payload
        assert any(goal.get("id") == GOAL_ID for goal in global_payload.get("goals") or []), global_payload

        ready_gate = run_promotion_gate(env, runtime)
        assert ready_gate["ok"] is True, ready_gate
        assert ready_gate["gate_state"] == "ready", ready_gate
        assert ready_gate["can_promote"] is True, ready_gate
        assert ready_gate["should_warn"] is False, ready_gate
        assert "warning_message" not in ready_gate, ready_gate
        assert ready_gate["readiness"]["freshness_status"] == "fresh", ready_gate
        assert ready_gate["readiness"]["requires_readiness_run"] is False, ready_gate
        assert ready_gate["readiness"]["classification"] == module.READINESS_CLASSIFICATION, ready_gate

        post_install = run_install(env, "after-readiness-evidence")
        assert "loopx installed locally" in post_install.stdout, post_install.stdout
        assert "promotion-readiness evidence is missing" not in post_install.stderr, post_install.stderr
        assert "promotion-readiness evidence is stale" not in post_install.stderr, post_install.stderr
        assert "loopx install warning: promotion-readiness evidence" not in post_install.stderr, post_install.stderr

        doctor = subprocess.run(
            [str(home / ".local" / "bin" / "loopx"), "--format", "json", "doctor"],
            cwd=REPO_ROOT,
            env={**env, "PATH": f"{home / '.local' / 'bin'}:{env.get('PATH', '')}"},
            check=True,
            capture_output=True,
            text=True,
        )
        doctor_payload = json.loads(doctor.stdout)
        readiness = doctor_payload["release_provenance"]["promotion_readiness"]
        assert readiness["available"] is True, readiness
        assert readiness["freshness_status"] == "fresh", readiness
        assert readiness["requires_readiness_run"] is False, readiness
        assert readiness["classification"] == module.READINESS_CLASSIFICATION, readiness

    print("canary-promotion-readiness-writeback-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
