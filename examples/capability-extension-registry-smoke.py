#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


with tempfile.TemporaryDirectory(prefix="loopx-extension-registry-") as raw_temp:
    manifest = Path(raw_temp) / "extension.toml"
    manifest.write_text(
        """\
schema_version = "loopx_extension_manifest_v0"
id = "example-extension"
version = "1.0.0"
requires_loopx_api = ">=1,<2"
permissions = ["read_status"]

[[provides]]
id = "example-report"
kind = "projection_sink"
title = "Example report"
status = "active"
visibility = "public"
real_world_anchor = "public smoke fixture"
user_value = "Prove explicit extension composition."
entry_command = "example-extension report"
next_real_step = "Keep explicit enablement bounded."
""",
        encoding="utf-8",
    )

    baseline = run_cli("capability", "list")
    assert [item["id"] for item in baseline["capabilities"]] == [
        "issue-fix",
        "semantic-preference",
        "reward-memory",
        "periodic-report",
        "content-ops",
        "value-connectors",
    ]
    assert all(item["provider_id"] == "loopx-core" for item in baseline["capabilities"])

    composed = run_cli(
        "capability",
        "list",
        "--extension-manifest",
        str(manifest),
    )
    assert composed["capabilities"][-1]["id"] == "example-report"
    assert composed["capabilities"][-1]["origin"] == "extension"
    assert composed["providers"][-1]["id"] == "example-extension"

    detail = run_cli(
        "capability",
        "show",
        "example-report",
        "--extension-manifest",
        str(manifest),
    )
    assert detail["capability"]["capability_kind"] == "projection_sink"
    assert detail["capability"]["provider_id"] == "example-extension"

    lark_manifest = ROOT / "loopx" / "extensions" / "lark" / "extension.toml"
    lark = run_cli(
        "capability",
        "show",
        "lark-event-inbox",
        "--extension-manifest",
        str(lark_manifest),
    )
    assert lark["capability"]["origin"] == "extension", lark
    assert lark["capability"]["provider_id"] == "loopx-lark", lark

print("capability-extension-registry-smoke: ok")
