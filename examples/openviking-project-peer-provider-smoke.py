#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix import build_issue_fix_pr_description  # noqa: E402
from loopx.extensions.openviking_semantic_preference.project_peer import (  # noqa: E402
    resolve_project_peer_scope,
)
from loopx.repository_identity import normalize_repository_identity  # noqa: E402


REMOTE = "https://github.com/volcengine/OpenViking.git"
WRONG_REMOTE = "https://github.com/example/Other.git"
REQUEST = {
    "schema_version": "semantic_preference_provider_request_v0",
    "surface": "issue_fix.pr_description",
    "query": "PR description structure and validation preferences",
    "limit": 3,
    "context": {"repository": "volcengine/OpenViking"},
}


def provider_command(
    *,
    project: Path,
    ov_bin: Path,
    cli_config: Path,
    remote_url: str,
    fallback: bool = False,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "loopx.cli",
        "semantic-preference",
        "openviking-provider",
        "--project",
        str(project),
        "--remote-url",
        remote_url,
        "--ov-bin",
        str(ov_bin),
        "--cli-config",
        str(cli_config),
        "--user-space",
        "pilot",
    ]
    if fallback:
        command.extend(["--include-global-fallback", "--max-find-calls", "2"])
    return command


def run_provider(
    command: Sequence[str], environment: Mapping[str, str]
) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        input=json.dumps(REQUEST),
        capture_output=True,
        check=False,
        env=dict(environment),
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["schema_version"] == "semantic_preference_provider_response_v0"
    return payload


def read_calls(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


identities = {
    normalize_repository_identity(value)
    for value in (
        "git@github.com:volcengine/OpenViking.git",
        "ssh://git@github.com/volcengine/OpenViking.git",
        REMOTE,
        "git:github.com/volcengine/OpenViking",
    )
}
assert identities == {"git:github.com/volcengine/OpenViking"}, identities
for unsafe_identity in (
    "ftp://example.invalid/repository",
    "git:github.com/volcengine/../private",
    "git:github.com/volcengine/OpenViking?unsupported=query",
):
    try:
        normalize_repository_identity(unsafe_identity)
    except ValueError:
        pass
    else:
        raise AssertionError(f"unsafe repository identity accepted: {unsafe_identity}")

with tempfile.TemporaryDirectory(prefix="loopx-openviking-project-peer-") as raw_temp:
    temp = Path(raw_temp)
    project = temp / "project"
    project.mkdir()
    log = temp / "ov-calls.jsonl"
    cli_config = temp / "openviking.conf"
    cli_config.write_text("local-only", encoding="utf-8")
    expected = resolve_project_peer_scope(
        project, user_space="pilot", remote_url=REMOTE
    )
    wrong = resolve_project_peer_scope(
        project, user_space="pilot", remote_url=WRONG_REMOTE
    )
    assert expected.peer_id != wrong.peer_id
    assert expected.recall_targets() == (expected.memory_uri,)
    assert expected.recall_targets(include_global_fallback=True)[1] == (
        "viking://user/pilot/memories"
    )

    fallback_scope = resolve_project_peer_scope(
        project, user_space="pilot", loopx_project_id="docs-agent"
    )
    assert fallback_scope.project_identity == "loopx:docs-agent"

    ov_bin = temp / "ov"
    ov_bin.write_text(
        """#!/usr/bin/env python3
import json, os, pathlib, sys

args = sys.argv[1:]
with pathlib.Path(os.environ["FAKE_OV_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args) + "\\n")
if os.environ.get("FAKE_OV_FAIL") == "1":
    raise SystemExit(7)
command_args = args
if args[:1] == ["--actor-peer-id"]:
    command_args = args[2:]
if command_args[0] == "status":
    result = {"healthy": True}
elif command_args[0] == "find":
    target = command_args[command_args.index("-u") + 1]
    expected = os.environ["EXPECTED_PROJECT_TARGET"]
    global_target = os.environ["EXPECTED_GLOBAL_TARGET"]
    if target == expected:
        memories = [{
            "uri": target + "/preferences/pr-description.md",
            "abstract": "For this repository, keep a concise Validation section.",
        }]
    elif target == global_target:
        memories = [{
            "uri": target + "/preferences/global.md",
            "abstract": "Use the global fallback only when explicitly requested.",
        }]
    else:
        memories = []
    result = {"memories": memories}
else:
    raise SystemExit(9)
print(json.dumps({"ok": True, "result": result}))
""",
        encoding="utf-8",
    )
    ov_bin.chmod(0o755)
    environment = dict(os.environ)
    environment.update(
        {
            "FAKE_OV_LOG": str(log),
            "EXPECTED_PROJECT_TARGET": expected.memory_uri,
            "EXPECTED_GLOBAL_TARGET": expected.global_memory_uri,
        }
    )

    describe = subprocess.run(
        [
            *provider_command(
                project=project,
                ov_bin=ov_bin,
                cli_config=cli_config,
                remote_url=REMOTE,
            ),
            "--describe-scope",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )
    assert describe.returncode == 0, describe.stderr
    described = json.loads(describe.stdout)
    assert described["peer_id"] == expected.peer_id
    assert described["memory_uri"] == expected.memory_uri
    described_inventory = described["corpus_inventory"]
    assert len(described_inventory) == 1, described_inventory
    assert described_inventory[0]["corpus_id"] == "project_peer_preferences"
    assert described_inventory[0]["scope_ref"] == expected.preferences_uri
    assert described_inventory[0]["write_actor_ref"] == expected.peer_id
    assert str(project) not in describe.stdout
    assert REMOTE not in describe.stdout
    assert read_calls(log) == [], "describe-scope must not contact OpenViking"

    doctor = subprocess.run(
        [
            *provider_command(
                project=project,
                ov_bin=ov_bin,
                cli_config=cli_config,
                remote_url=REMOTE,
            ),
            "--doctor",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )
    assert doctor.returncode == 0, doctor.stderr
    assert read_calls(log)[-1][0] == "status"

    log.unlink()
    recalled = run_provider(
        provider_command(
            project=project,
            ov_bin=ov_bin,
            cli_config=cli_config,
            remote_url=REMOTE,
        ),
        environment,
    )
    assert len(recalled["items"]) == 1, recalled
    assert recalled["corpus_inventory"][0]["scope_ref"] == (
        expected.preferences_uri
    )
    calls = read_calls(log)
    assert len(calls) == 1, calls
    assert calls[0][:3] == ["--actor-peer-id", expected.peer_id, "find"]
    assert calls[0][calls[0].index("-u") + 1] == expected.memory_uri

    log.unlink()
    wrong_result = run_provider(
        provider_command(
            project=project,
            ov_bin=ov_bin,
            cli_config=cli_config,
            remote_url=WRONG_REMOTE,
        ),
        environment,
    )
    assert wrong_result["items"] == [], wrong_result
    calls = read_calls(log)
    assert len(calls) == 1, "no implicit global fallback is allowed"
    assert calls[0][:3] == ["--actor-peer-id", wrong.peer_id, "find"]

    log.unlink()
    fallback_result = run_provider(
        provider_command(
            project=project,
            ov_bin=ov_bin,
            cli_config=cli_config,
            remote_url=WRONG_REMOTE,
            fallback=True,
        ),
        environment,
    )
    assert len(fallback_result["items"]) == 1, fallback_result
    assert [
        item["corpus_id"] for item in fallback_result["corpus_inventory"]
    ] == ["project_peer_preferences", "user_global_preferences"]
    calls = read_calls(log)
    assert len(calls) == 2, calls
    assert all(call[:3] == ["--actor-peer-id", wrong.peer_id, "find"] for call in calls)
    assert calls[-1][calls[-1].index("-u") + 1] == expected.global_memory_uri

    config = temp / "semantic-preference.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "semantic_preference_hook_config_v0",
                "enabled": True,
                "provider": {
                    "argv": provider_command(
                        project=project,
                        ov_bin=ov_bin,
                        cli_config=cli_config,
                        remote_url=REMOTE,
                    ),
                    "timeout_seconds": 30,
                },
                "surfaces": {
                    "issue_fix.pr_description": {
                        "query": "PR description structure and validation preferences",
                        "limit": 3,
                        "failure_policy": "fail_open",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    previous = {
        key: os.environ.get(key)
        for key in ("FAKE_OV_LOG", "EXPECTED_PROJECT_TARGET", "EXPECTED_GLOBAL_TARGET")
    }
    os.environ.update(
        {
            "FAKE_OV_LOG": str(log),
            "EXPECTED_PROJECT_TARGET": expected.memory_uri,
            "EXPECTED_GLOBAL_TARGET": expected.global_memory_uri,
        }
    )

    def apply_preferences(
        base: str, items: Sequence[Mapping[str, object]]
    ) -> Mapping[str, object]:
        return {
            "description": f"{base}\n\n## Validation\n\nRun focused checks.\n",
            "applied_preference_refs": [items[0]["preference_ref"]],
        }

    built = build_issue_fix_pr_description(
        "## Motivation\n\nFix the reproduced behavior.",
        project=project,
        semantic_preference_config=config,
        context=("repository=volcengine/OpenViking",),
        application_id="project-peer-provider-smoke",
        artifact_ref="project-peer-provider-smoke",
        apply_preferences=apply_preferences,
    )
    assert built["semantic_preference"]["application_status"] == "applied", built
    assert built["semantic_preference"]["receipt"]["outcome"] == "applied", built
    assert built["semantic_preference"]["corpus_inventory"][0]["corpus_id"] == (
        "project_peer_preferences"
    ), built
    assert built["semantic_preference"]["maintenance_guidance"]["completion"] == (
        "provider_write_then_wait_l2_read_and_scoped_recall"
    ), built
    assert built["raw_preference_content_returned"] is False

    os.environ["FAKE_OV_FAIL"] = "1"
    failed_open = build_issue_fix_pr_description(
        "## Motivation\n\nPreserve this base.",
        project=project,
        semantic_preference_config=config,
        application_id="project-peer-provider-fail-open",
        apply_preferences=apply_preferences,
    )
    os.environ.pop("FAKE_OV_FAIL", None)
    assert failed_open["fail_open_preserved_base"] is True, failed_open
    assert failed_open["description"] == "## Motivation\n\nPreserve this base."

    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

print("OpenViking project peer provider smoke: ok")
