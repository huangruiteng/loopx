#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.extensions.lark.event_collector import (  # noqa: E402
    inspect_lark_event_collector,
    install_lark_event_collector,
    plan_lark_event_collector,
)
from loopx.extensions.lark.event_collector_runtime import (  # noqa: E402
    enrich_lark_event_reply_context,
    lark_event_requires_reply_context_lookup,
    run_lark_event_collector,
)
from loopx.extensions.lark.event_inbox import (  # noqa: E402
    project_lark_event_inbox_urgency,
)


def completed(argv: list[str], returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout="", stderr="")


with tempfile.TemporaryDirectory(prefix="loopx-lark-collector-") as raw:
    temp = Path(raw)
    project = temp / "project"
    home = temp / "home"
    bin_dir = temp / "bin"
    project.mkdir()
    home.mkdir()
    bin_dir.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / ".gitignore").write_text(".loopx/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(project), "add", ".gitignore"], check=True)
    lark_cli = bin_dir / "lark-cli"
    lark_cli.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    lark_cli.chmod(0o755)
    node = bin_dir / "node"
    node.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    node.chmod(0o755)
    config_dir = project / ".loopx" / "config" / "lark"
    config_dir.mkdir(parents=True)
    inbox_config = config_dir / "event-inbox.json"
    inbox_config.write_text(
        json.dumps(
            {
                "schema_version": "lark_event_inbox_config_v0",
                "enabled": True,
                "inbox_dir": ".loopx/inbox/team-feedback",
                "capture_scope": "configured_chat_all",
                "reply": {
                    "enabled": True,
                    "sender_profile": "project-review-bot",
                    "sender_identity": "bot",
                    "bot_display_name": "Project Review Bot",
                    "chat_id": "oc_private_fixture_chat",
                },
            }
        ),
        encoding="utf-8",
    )
    collector_config = config_dir / "collector.json"
    collector_config.write_text(
        json.dumps(
            {
                "schema_version": "lark_event_collector_config_v0",
                "enabled": True,
                "service_name": "loopx-lark-feedback",
                "event_key": "im.message.receive_v1",
                "identity": "bot",
                "supervisor": "launchd",
                "chat_id": "oc_private_fixture_chat",
                "consume_timeout": "30m",
                "lark_cli_bin": "lark-cli",
                "event_inbox_config": ".loopx/config/lark/event-inbox.json",
            }
        ),
        encoding="utf-8",
    )
    previous_home = os.environ.get("HOME")
    previous_path = os.environ.get("PATH")
    os.environ["HOME"] = str(home)
    os.environ["PATH"] = f"{bin_dir}:{previous_path or ''}"
    runtime_root = temp / "runtime"
    installed_extension = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--runtime-root",
            str(runtime_root),
            "--format",
            "json",
            "extension",
            "install",
            "--bundled",
            "loopx-lark",
            "--execute",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert installed_extension.returncode == 0, installed_extension.stderr
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        if argv[:2] == ["launchctl", "print"]:
            return subprocess.CompletedProcess(
                argv, 0, stdout="state = running\n", stderr=""
            )
        return completed(argv)

    try:
        plan = plan_lark_event_collector(
            project=project,
            config_path=collector_config,
            runtime_root=runtime_root,
        )
        assert plan["status"] == "install_ready", plan
        assert plan["thread_complete"] is True, plan
        assert plan["profile_bound"] is True, plan
        assert plan["profile_source"] == "event_inbox_reply", plan
        assert plan["profile_returned"] is False, plan
        assert "project-review-bot" not in json.dumps(plan), plan
        assert plan["chat_id_returned"] is False, plan
        assert "oc_private_fixture_chat" not in json.dumps(plan), plan
        preview = install_lark_event_collector(
            project=project,
            config_path=collector_config,
            runtime_root=runtime_root,
            runner=runner,
        )
        assert preview["status"] == "preview_ready", preview
        assert preview["would_write_service"] is True, preview
        assert calls == [
            [str(node), str(lark_cli), "event", "consume", "--help"]
        ], calls

        installed = install_lark_event_collector(
            project=project,
            config_path=collector_config,
            runtime_root=runtime_root,
            execute=True,
            runner=runner,
        )
        assert installed["status"] == "installed", installed
        assert installed["write_performed"] is True, installed
        assert any(call[:2] == ["launchctl", "bootstrap"] for call in calls), calls
        plist = home / "Library" / "LaunchAgents" / "loopx-lark-feedback.plist"
        assert plist.is_file(), plist
        plist_text = plist.read_text(encoding="utf-8")
        assert str(node) in plist_text, plist_text
        assert str(lark_cli) in plist_text, plist_text
        service_argv = plistlib.loads(plist.read_bytes())["ProgramArguments"]
        assert Path(service_argv[0]).name == "loopx", service_argv
        assert service_argv[1:3] == [
            "--runtime-root",
            str(runtime_root.resolve()),
        ], service_argv
        assert service_argv[3:5] == ["lark-inbox", "collector-run"], service_argv
        assert service_argv[service_argv.index("--lark-cli-executable") + 1] == str(
            lark_cli
        ), service_argv
        assert service_argv[service_argv.index("--node-executable") + 1] == str(
            node
        ), service_argv
        assert "event" not in service_argv and "consume" not in service_argv, service_argv

        direct_event = {
            "message_id": "om_direct_fixture",
            "content": "@Project Review Bot 请处理这个问题",
        }
        assert not lark_event_requires_reply_context_lookup(
            direct_event,
            bot_display_name="Project Review Bot",
        )
        assert lark_event_requires_reply_context_lookup(
            {"message_id": "om_plain_fixture", "content": "普通群聊消息"},
            bot_display_name="Project Review Bot",
        )

        messages = {
            "om_reply_fixture": {
                "message_id": "om_reply_fixture",
                "parent_id": "om_bot_parent",
                "root_id": "om_bot_parent",
                "chat_id": "oc_private_fixture_chat",
                "sender": {"sender_type": "user", "id": "ou_fixture_user"},
            },
            "om_bot_parent": {
                "message_id": "om_bot_parent",
                "chat_id": "oc_private_fixture_chat",
                "sender": {"sender_type": "app", "id": "cli_fixture_app"},
            },
            "om_human_reply": {
                "message_id": "om_human_reply",
                "parent_id": "om_human_parent",
                "chat_id": "oc_private_fixture_chat",
                "sender": {"sender_type": "user", "id": "ou_fixture_user"},
            },
            "om_human_parent": {
                "message_id": "om_human_parent",
                "chat_id": "oc_private_fixture_chat",
                "sender": {"sender_type": "user", "id": "ou_fixture_other"},
            },
        }
        lookup_calls: list[list[str]] = []

        def lookup_runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            lookup_calls.append(list(argv))
            message_id = argv[argv.index("--message-ids") + 1]
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps({"items": [messages[message_id]]}),
                stderr="",
            )

        bot_reply = enrich_lark_event_reply_context(
            {"message_id": "om_reply_fixture", "content": "继续"},
            runner=lookup_runner,
            command_prefix=["lark-cli"],
            profile="project-review-bot",
            profile_app_id="cli_fixture_app",
            configured_chat_id="oc_private_fixture_chat",
            sleeper=lambda _: None,
        )
        assert bot_reply["reply_context_verified"] is True, bot_reply
        assert bot_reply["reply_to_bot"] is True, bot_reply
        human_reply = enrich_lark_event_reply_context(
            {"message_id": "om_human_reply", "content": "继续"},
            runner=lookup_runner,
            command_prefix=["lark-cli"],
            profile="project-review-bot",
            profile_app_id="cli_fixture_app",
            configured_chat_id="oc_private_fixture_chat",
            sleeper=lambda _: None,
        )
        assert human_reply["reply_context_verified"] is True, human_reply
        assert human_reply["reply_to_bot"] is False, human_reply
        assert all(
            call[:3] == ["lark-cli", "--profile", "project-review-bot"]
            for call in lookup_calls
        ), lookup_calls

        inbox = project / ".loopx" / "inbox" / "team-feedback"
        inbox.mkdir(parents=True)
        (inbox / "om_fixture.json").write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_event_v0",
                    "event_id": "om_fixture",
                    "message_id": "om_fixture",
                    "create_time": "1",
                    "content": "public-safe fixture",
                }
            ),
            encoding="utf-8",
        )
        status = inspect_lark_event_collector(
            project=project,
            config_path=collector_config,
            runtime_root=runtime_root,
            probe_event_bus=True,
            runner=runner,
        )
        assert status["healthy"] is True, status
        assert status["real_event_evidence_present"] is True, status
        assert status["captured_event_count"] == 1, status
        assert status["profile_bound"] is True, status
        assert status["profile_source"] == "event_inbox_reply", status
        assert status["profile_returned"] is False, status
        assert "project-review-bot" not in json.dumps(status), status
        assert status["local_paths_returned"] is False, status
        assert status["chat_id_returned"] is False, status

        runtime_cli = bin_dir / "runtime-lark-cli"
        runtime_cli.write_text(
            """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
messages = {
    "om_runtime_ordinary": {
        "message_id": "om_runtime_ordinary",
        "chat_id": "oc_private_fixture_chat",
        "sender": {"sender_type": "user", "id": "ou_fixture_user"},
    },
    "om_runtime_reply": {
        "message_id": "om_runtime_reply",
        "parent_id": "om_runtime_bot_parent",
        "chat_id": "oc_private_fixture_chat",
        "sender": {"sender_type": "user", "id": "ou_fixture_user"},
    },
    "om_runtime_bot_parent": {
        "message_id": "om_runtime_bot_parent",
        "chat_id": "oc_private_fixture_chat",
        "sender": {"sender_type": "app", "id": "cli_fixture_app"},
    },
}
if "event" in args and "consume" in args:
    events = [
        {
            "schema_version": "lark_event_inbox_event_v0",
            "event_id": "evt-runtime-direct",
            "message_id": "om_runtime_direct",
            "create_time": "2026-07-16T00:00:00Z",
            "content": "@Project Review Bot 能处理吗？",
        },
        {
            "schema_version": "lark_event_inbox_event_v0",
            "event_id": "evt-runtime-ordinary",
            "message_id": "om_runtime_ordinary",
            "create_time": "2026-07-16T00:01:00Z",
            "content": "Project Review Bot 群里的普通问题为什么会这样？",
        },
        {
            "schema_version": "lark_event_inbox_event_v0",
            "event_id": "evt-runtime-reply",
            "message_id": "om_runtime_reply",
            "create_time": "2026-07-16T00:02:00Z",
            "content": "这是不带 at 的回复",
        },
    ]
    for event in events:
        print(json.dumps(event), flush=True)
elif "whoami" in args:
    print(json.dumps({"appId": "cli_fixture_app"}))
elif "+messages-mget" in args:
    message_id = args[args.index("--message-ids") + 1]
    print(json.dumps({"items": [messages[message_id]]}))
else:
    raise SystemExit(2)
""",
            encoding="utf-8",
        )
        runtime_cli.chmod(0o755)
        runtime_result = run_lark_event_collector(
            project=project,
            config_path=collector_config,
            lark_cli_executable=str(runtime_cli),
        )
        assert runtime_result["ok"] is True, runtime_result
        assert runtime_result["captured_count"] == 3, runtime_result
        assert runtime_result["reply_context_verified_count"] == 2, runtime_result
        assert runtime_result["reply_to_bot_count"] == 1, runtime_result
        runtime_urgency = project_lark_event_inbox_urgency(
            project=project,
            config_path=inbox_config,
        )
        assert runtime_urgency["direct_question_count"] == 1, runtime_urgency
        assert runtime_urgency["reply_to_bot_count"] == 1, runtime_urgency
        assert runtime_urgency["attention_required_count"] == 2, runtime_urgency

        unsupported = json.loads(collector_config.read_text())
        unsupported["event_key"] = "im.message.reaction.created_v1"
        collector_config.write_text(json.dumps(unsupported), encoding="utf-8")
        try:
            plan_lark_event_collector(
                project=project,
                config_path=collector_config,
            )
        except ValueError as exc:
            assert "im.message.receive_v1" in str(exc), exc
        else:
            raise AssertionError("unsupported event key should fail closed")
        unsupported["event_key"] = "im.message.receive_v1"
        unsupported["identity"] = "user"
        collector_config.write_text(json.dumps(unsupported), encoding="utf-8")
        try:
            plan_lark_event_collector(
                project=project,
                config_path=collector_config,
            )
        except ValueError as exc:
            assert "identity must be bot" in str(exc), exc
        else:
            raise AssertionError("unsupported identity should fail closed")
        unsupported["identity"] = "bot"
        collector_config.write_text(json.dumps(unsupported), encoding="utf-8")

        mismatched = json.loads(collector_config.read_text())
        mismatched["profile"] = "another-review-bot"
        collector_config.write_text(json.dumps(mismatched), encoding="utf-8")
        try:
            plan_lark_event_collector(
                project=project,
                config_path=collector_config,
            )
        except ValueError as exc:
            assert "must match" in str(exc), exc
        else:
            raise AssertionError("collector and reply profiles must not diverge")
        mismatched.pop("profile")
        collector_config.write_text(json.dumps(mismatched), encoding="utf-8")

        no_profile = json.loads(inbox_config.read_text())
        no_profile.pop("reply")
        inbox_config.write_text(json.dumps(no_profile), encoding="utf-8")
        try:
            plan_lark_event_collector(
                project=project,
                config_path=collector_config,
            )
        except ValueError as exc:
            assert "explicit non-default profile" in str(exc), exc
        else:
            raise AssertionError("enabled collector must not use the default profile")
        explicit = json.loads(collector_config.read_text())
        explicit["profile"] = "project-review-bot"
        collector_config.write_text(json.dumps(explicit), encoding="utf-8")
        explicit_plan = plan_lark_event_collector(
            project=project,
            config_path=collector_config,
        )
        assert explicit_plan["profile_source"] == "collector_config", explicit_plan
        explicit.pop("profile")
        collector_config.write_text(json.dumps(explicit), encoding="utf-8")
        no_profile["reply"] = {
            "enabled": True,
            "sender_profile": "project-review-bot",
            "sender_identity": "bot",
            "bot_display_name": "Project Review Bot",
            "chat_id": "oc_private_fixture_chat",
        }
        inbox_config.write_text(json.dumps(no_profile), encoding="utf-8")

        addressed = json.loads(inbox_config.read_text())
        addressed["capture_scope"] = "addressed_only"
        inbox_config.write_text(json.dumps(addressed), encoding="utf-8")
        failed = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "--runtime-root",
                str(runtime_root),
                "lark-inbox",
                "collector-plan",
                "--project",
                str(project),
                "--config",
                str(collector_config),
            ],
            cwd=ROOT,
            env=os.environ,
            capture_output=True,
            text=True,
            check=False,
        )
        assert failed.returncode == 1, failed.stdout
        error = json.loads(failed.stdout)
        assert "configured_chat_all" in error["error"], error
    finally:
        if previous_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = previous_home
        if previous_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = previous_path

print("lark event collector lifecycle smoke: ok")
