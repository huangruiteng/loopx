#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    registry: Path,
    runtime_root: Path,
    *args: str,
    expected_returncode: int = 0,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
            "--runtime-root",
            str(runtime_root),
            "--format",
            "json",
            *args,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == expected_returncode, completed
    return json.loads(completed.stdout)


with tempfile.TemporaryDirectory(prefix="loopx-lark-extension-") as raw_temp:
    temp = Path(raw_temp)
    project = temp / "project"
    runtime_root = temp / "runtime"
    project.mkdir()
    config = project / ".loopx" / "config" / "lark-event-inbox.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "schema_version": "lark_event_inbox_config_v0",
                "enabled": True,
                "inbox_dir": ".loopx/inbox/lark-feedback",
            }
        ),
        encoding="utf-8",
    )
    reviewer_config = project / ".loopx" / "config" / "reviewer-notifications.json"
    reviewer_config.write_text(
        json.dumps(
            {
                "schema_version": "issue_fix_reviewer_notification_sinks_input_v0",
                "feedback_inbox_config": ".loopx/config/lark-event-inbox.json",
                "sinks": [
                    {
                        "sink_kind": "lark_chat",
                        "reader_profile": "fixture-reader",
                        "reader_identity": "user",
                        "sender_profile": "fixture-bot",
                        "sender_identity": "bot",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    registry = project / ".loopx" / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": "lark-extension-fixture",
                        "repo": str(project),
                        "control_plane": {
                            "lark_event_inbox": {
                                "enabled": True,
                                "config_path": ".loopx/config/lark-event-inbox.json",
                            },
                            "issue_fix": {
                                "reviewer_notification": {
                                    "enabled": True,
                                    "config_path": (
                                        ".loopx/config/reviewer-notifications.json"
                                    ),
                                }
                            },
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    drain_args = (
        "lark-inbox",
        "drain",
        "--goal-id",
        "lark-extension-fixture",
    )
    reviewer_drain_args = (
        "issue-fix",
        "reviewer-feedback-inbox",
        "--goal-id",
        "lark-extension-fixture",
    )

    missing = run_cli(
        registry,
        runtime_root,
        *drain_args,
        expected_returncode=1,
    )
    assert "not installed" in str(missing["error"]), missing
    reviewer_missing = run_cli(
        registry,
        runtime_root,
        *reviewer_drain_args,
        expected_returncode=1,
    )
    assert "not installed" in str(reviewer_missing["error"]), reviewer_missing

    installed = run_cli(
        registry,
        runtime_root,
        "extension",
        "install",
        "--bundled",
        "loopx-lark",
        "--execute",
    )
    assert installed["doctor"]["verified"] is True, installed
    active = run_cli(registry, runtime_root, *drain_args)
    assert active["extension_activation"] == {
        "schema_version": "loopx_extension_activation_v0",
        "extension_id": "loopx-lark",
        "provider_version": "1.1.0",
        "revision": installed["revision"],
        "enabled": True,
        "doctor_verified": True,
        "required_permissions": ["lark.inbox.read"],
    }, active
    reviewer_active = run_cli(registry, runtime_root, *reviewer_drain_args)
    assert reviewer_active["configured_reviewer_group"] is True, reviewer_active
    assert reviewer_active["extension_activation"] == {
        **active["extension_activation"],
        "required_permissions": [
            "lark.inbox.read",
            "lark.inbox.write",
            "lark.reply.send",
            "lark.reviewer_notification.send",
        ],
    }, reviewer_active

    disabled = run_cli(
        registry,
        runtime_root,
        "extension",
        "disable",
        "loopx-lark",
        "--execute",
    )
    assert disabled["enabled"] is False, disabled
    blocked = run_cli(
        registry,
        runtime_root,
        *drain_args,
        expected_returncode=1,
    )
    assert "is disabled" in str(blocked["error"]), blocked
    reviewer_blocked = run_cli(
        registry,
        runtime_root,
        *reviewer_drain_args,
        expected_returncode=1,
    )
    assert "is disabled" in str(reviewer_blocked["error"]), reviewer_blocked

    enabled = run_cli(
        registry,
        runtime_root,
        "extension",
        "enable",
        "loopx-lark",
        "--execute",
    )
    assert enabled["doctor"]["verified"] is True, enabled

    bundled_manifest = ROOT / "loopx" / "extensions" / "lark" / "extension.toml"
    upgraded_manifest = temp / "loopx-lark-v1.1.toml"
    upgraded_manifest.write_text(
        bundled_manifest.read_text(encoding="utf-8").replace(
            'version = "1.1.0"',
            'version = "1.2.0"',
            1,
        ),
        encoding="utf-8",
    )
    upgraded = run_cli(
        registry,
        runtime_root,
        "extension",
        "upgrade",
        "--manifest",
        str(upgraded_manifest),
        "--execute",
    )
    assert upgraded["previous_revision"] == installed["revision"], upgraded
    after_upgrade = run_cli(registry, runtime_root, *drain_args)
    assert after_upgrade["extension_activation"]["revision"] == upgraded["revision"]
    reviewer_after_upgrade = run_cli(registry, runtime_root, *reviewer_drain_args)
    assert (
        reviewer_after_upgrade["extension_activation"]["revision"]
        == upgraded["revision"]
    )

    rolled_back = run_cli(
        registry,
        runtime_root,
        "extension",
        "rollback",
        "loopx-lark",
        "--execute",
    )
    assert rolled_back["revision"] == installed["revision"], rolled_back
    after_rollback = run_cli(registry, runtime_root, *drain_args)
    assert (
        after_rollback["extension_activation"]["revision"] == installed["revision"]
    ), after_rollback

    doctor = run_cli(
        registry,
        runtime_root,
        "extension",
        "doctor",
        "loopx-lark",
        "--execute",
    )
    assert doctor["verified"] is True, doctor

print("lark-extension-activation-smoke: ok")
