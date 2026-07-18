#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def write_provider(path: Path, label: str) -> Path:
    path.write_text(
        f"""#!{sys.executable}
import json
import sys

if "--doctor" in sys.argv:
    raise SystemExit(0)
request = json.load(sys.stdin)
json.dump({{
    "schema_version": "semantic_preference_provider_response_v0",
    "items": [{{
        "preference_ref": "provider://preference/{label}",
        "summary": "{label}",
    }}],
}}, sys.stdout)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def write_manifest(path: Path, provider: Path, version: str) -> Path:
    path.write_text(
        f"""\
schema_version = "loopx_extension_manifest_v0"
id = "smoke-semantic-extension"
version = "{version}"
requires_loopx_api = ">=1,<2"
permissions = ["semantic_preference.read"]

[runtime]
protocol = "semantic_preference_provider_v0"
entrypoint = {json.dumps(str(provider))}
doctor_args = ["--doctor"]
required_permissions = ["semantic_preference.read"]
timeout_seconds = 5

[[implements]]
capability_id = "semantic-preference"
protocol = "semantic_preference_provider_v0"
""",
        encoding="utf-8",
    )
    return path


with tempfile.TemporaryDirectory(prefix="loopx-extension-runtime-") as raw_temp:
    temp = Path(raw_temp)
    runtime_root = temp / "runtime"
    state_file = runtime_root / "extensions" / "state.json"
    project = temp / "project"
    project.mkdir()
    v1 = write_manifest(
        temp / "v1.toml",
        write_provider(temp / "provider-v1", "provider-v1"),
        "1.0.0",
    )
    v2 = write_manifest(
        temp / "v2.toml",
        write_provider(temp / "provider-v2", "provider-v2"),
        "2.0.0",
    )
    config = temp / "semantic-preference.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": True,
                "provider": {
                    "id": "smoke_semantic_extension",
                    "extension_id": "smoke-semantic-extension",
                },
                "surfaces": {
                    "issue_fix.pr_description": {
                        "query": "validation preferences",
                        "failure_policy": "fail_open",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    installed = run_cli(
        "--runtime-root",
        str(runtime_root),
        "extension",
        "install",
        "--manifest",
        str(v1),
        "--execute",
    )
    assert installed["doctor"]["verified"] is True
    first = run_cli(
        "--runtime-root",
        str(runtime_root),
        "semantic-preference",
        "recall",
        "--project",
        str(project),
        "--config",
        str(config),
        "--surface",
        "issue_fix.pr_description",
        "--execute",
    )
    assert first["items"][0]["summary"] == "provider-v1"

    disabled = run_cli(
        "--runtime-root",
        str(runtime_root),
        "extension",
        "disable",
        "smoke-semantic-extension",
        "--execute",
    )
    assert disabled["enabled"] is False
    unavailable = run_cli(
        "--runtime-root",
        str(runtime_root),
        "semantic-preference",
        "recall",
        "--project",
        str(project),
        "--config",
        str(config),
        "--surface",
        "issue_fix.pr_description",
        "--execute",
    )
    assert unavailable["status"] == "provider_unavailable"
    assert unavailable["failure_kind"] == "extension_binding_unavailable"

    upgraded = run_cli(
        "--runtime-root",
        str(runtime_root),
        "extension",
        "upgrade",
        "--manifest",
        str(v2),
        "--execute",
    )
    assert upgraded["previous_revision"] == installed["revision"]
    second = run_cli(
        "--runtime-root",
        str(runtime_root),
        "semantic-preference",
        "recall",
        "--project",
        str(project),
        "--config",
        str(config),
        "--surface",
        "issue_fix.pr_description",
        "--execute",
    )
    assert second["items"][0]["summary"] == "provider-v2"

    rolled_back = run_cli(
        "--runtime-root",
        str(runtime_root),
        "extension",
        "rollback",
        "smoke-semantic-extension",
        "--execute",
    )
    assert rolled_back["revision"] == installed["revision"]
    final = run_cli(
        "--runtime-root",
        str(runtime_root),
        "semantic-preference",
        "recall",
        "--project",
        str(project),
        "--config",
        str(config),
        "--surface",
        "issue_fix.pr_description",
        "--execute",
    )
    assert final["items"][0]["summary"] == "provider-v1"

print("openviking-extension-runtime-smoke: ok")
