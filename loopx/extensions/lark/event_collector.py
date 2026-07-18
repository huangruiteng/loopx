from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .event_inbox import (
    SAFE_PROFILE_PATTERN,
    inspect_lark_event_inbox,
    load_lark_event_inbox_config,
)


CONFIG_SCHEMA_VERSION = "lark_event_collector_config_v0"
PLAN_SCHEMA_VERSION = "lark_event_collector_plan_v0"
STATUS_SCHEMA_VERSION = "lark_event_collector_status_v0"
INSTALL_SCHEMA_VERSION = "lark_event_collector_install_v0"
SERVICE_RE = re.compile(r"^loopx-[a-z0-9][a-z0-9._-]{1,73}$")
CHAT_RE = re.compile(r"^oc_[A-Za-z0-9_-]+$")
TIMEOUT_RE = re.compile(r"^[1-9][0-9]*(?:s|m|h)$")
SUPPORTED_SUPERVISORS = {"launchd", "systemd"}
SUPPORTED_EVENT_KEY = "im.message.receive_v1"

Runner = Callable[..., subprocess.CompletedProcess[str]]


def _project_config_path(project: str | Path, raw: str | Path) -> Path:
    root = Path(project).expanduser().resolve()
    path = Path(raw).expanduser()
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError("lark collector config must stay inside the project") from exc
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", str(relative)],
        capture_output=True,
        check=False,
    )
    ignored = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--quiet", "--", str(relative)],
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0 or ignored.returncode != 0:
        raise ValueError("lark collector config must be ignored and untracked")
    return path


def _relative_project_path(root: Path, raw: object, label: str) -> tuple[str, Path]:
    value = str(raw or "").strip().replace("\\", "/")
    if not value or value.startswith("/") or ".." in Path(value).parts:
        raise ValueError(f"{label} must be a project-relative path")
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes the project") from exc
    return value, path


def load_lark_event_collector_config(
    *, project: str | Path, config_path: str | Path
) -> dict[str, Any]:
    root = Path(project).expanduser().resolve()
    path = _project_config_path(root, config_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            "lark collector config must be a readable JSON object"
        ) from exc
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_version") != CONFIG_SCHEMA_VERSION
    ):
        raise ValueError(
            f"lark collector config schema_version must be {CONFIG_SCHEMA_VERSION}"
        )
    enabled = payload.get("enabled") is True
    service_name = str(payload.get("service_name") or "loopx-lark-collector").strip()
    event_key = str(payload.get("event_key") or "im.message.receive_v1").strip()
    identity = str(payload.get("identity") or "bot").strip()
    supervisor = str(payload.get("supervisor") or "").strip()
    chat_id = str(payload.get("chat_id") or "").strip()
    timeout = str(payload.get("consume_timeout") or "30m").strip()
    lark_cli_bin = str(payload.get("lark_cli_bin") or "lark-cli").strip()
    if not SERVICE_RE.fullmatch(service_name):
        raise ValueError("service_name must be a lowercase loopx- service token")
    if event_key != SUPPORTED_EVENT_KEY:
        raise ValueError(
            f"collector v0 event_key must be {SUPPORTED_EVENT_KEY}"
        )
    if identity != "bot":
        raise ValueError("collector v0 identity must be bot")
    if supervisor not in SUPPORTED_SUPERVISORS:
        raise ValueError("supervisor must be launchd or systemd")
    if not CHAT_RE.fullmatch(chat_id):
        raise ValueError("chat_id must be a Lark oc_ chat id")
    if not TIMEOUT_RE.fullmatch(timeout):
        raise ValueError("consume_timeout must use a bounded duration such as 30m")
    if Path(lark_cli_bin).name != lark_cli_bin or not lark_cli_bin:
        raise ValueError("lark_cli_bin must be a command name, not a path")
    inbox_config_ref, inbox_config_path = _relative_project_path(
        root, payload.get("event_inbox_config"), "event_inbox_config"
    )
    inbox = load_lark_event_inbox_config(project=root, config_path=inbox_config_path)
    if enabled and not inbox["enabled"]:
        raise ValueError("enabled collector requires an enabled event inbox")
    if enabled and not inbox["thread_complete"]:
        raise ValueError(
            "collector lifecycle currently requires configured_chat_all capture"
    )
    configured_profile = str(payload.get("profile") or "").strip()
    reply_profile = (
        str(inbox["reply"].get("sender_profile") or "").strip()
        if inbox["reply"].get("enabled") is True
        else ""
    )
    profile = configured_profile or reply_profile
    profile_source = None
    if configured_profile:
        profile_source = "collector_config"
    elif reply_profile:
        profile_source = "event_inbox_reply"
    if enabled and (
        not SAFE_PROFILE_PATTERN.fullmatch(profile)
        or profile.lower() == "default"
    ):
        raise ValueError(
            "enabled lark collector requires an explicit non-default profile "
            "or an enabled inbox reply sender_profile"
        )
    if configured_profile and reply_profile and configured_profile != reply_profile:
        raise ValueError(
            "lark collector profile must match the inbox reply sender_profile"
        )
    return {
        "enabled": enabled,
        "project": root,
        "config_path": path,
        "service_name": service_name,
        "event_key": event_key,
        "identity": identity,
        "profile": profile,
        "profile_source": profile_source,
        "supervisor": supervisor,
        "chat_id": chat_id,
        "consume_timeout": timeout,
        "lark_cli_bin": lark_cli_bin,
        "event_inbox_config_ref": inbox_config_ref,
        "inbox": inbox,
    }


def _jq_projection(chat_id: str) -> str:
    chat_literal = json.dumps(chat_id, ensure_ascii=False)
    return (
        f"select(.chat_id == {chat_literal}) | "
        '{schema_version:"lark_event_inbox_event_v0",'
        "event_id:(.event_id // .message_id),message_id:.message_id,"
        "create_time:.create_time,content:.content,sender_id:.sender_id,"
        "chat_id:.chat_id}"
    )


def _executable_prefix(executable: str) -> list[str]:
    path = Path(executable)
    try:
        first_line = path.open(encoding="utf-8").readline().strip()
    except (OSError, UnicodeDecodeError):
        return [executable]
    if first_line == "#!/usr/bin/env node":
        node = shutil.which("node")
        if node is None:
            raise ValueError(
                "lark-cli uses a Node wrapper but node is not available on PATH"
            )
        return [node, executable]
    return [executable]


def _collector_argv(config: Mapping[str, Any], executable: str) -> list[str]:
    prefix = _executable_prefix(executable)
    repo_root = Path(__file__).resolve().parents[3]
    discovered = shutil.which("loopx")
    loopx_executable = (
        Path(discovered) if discovered else repo_root / "scripts" / "loopx"
    )
    if not loopx_executable.is_file():
        raise ValueError("loopx executable is unavailable for collector runtime")
    argv = [
        str(loopx_executable),
        "lark-inbox",
        "collector-run",
        "--project",
        str(config["project"]),
        "--config",
        str(config["config_path"]),
        "--lark-cli-executable",
        executable,
    ]
    if len(prefix) == 2:
        argv.extend(["--node-executable", prefix[0]])
    return argv


def _service_file(config: Mapping[str, Any]) -> Path:
    name = str(config["service_name"])
    if config["supervisor"] == "launchd":
        return Path.home() / "Library" / "LaunchAgents" / f"{name}.plist"
    return Path.home() / ".config" / "systemd" / "user" / f"{name}.service"


def _service_payload(config: Mapping[str, Any], argv: Sequence[str]) -> bytes:
    root = Path(config["project"])
    runtime = root / ".loopx" / "runtime" / "lark-collector"
    if config["supervisor"] == "launchd":
        return plistlib.dumps(
            {
                "Label": str(config["service_name"]),
                "ProgramArguments": list(argv),
                "WorkingDirectory": str(root),
                "RunAtLoad": True,
                "KeepAlive": True,
                "ThrottleInterval": 5,
                "StandardOutPath": str(runtime / "collector.stdout.log"),
                "StandardErrorPath": str(runtime / "collector.stderr.log"),
            },
            sort_keys=True,
        )
    command = " ".join(shlex.quote(value) for value in argv)
    return (
        "[Unit]\nDescription=LoopX Lark event collector\nAfter=network-online.target\n\n"
        "[Service]\nType=simple\n"
        f"WorkingDirectory={root}\nExecStart={command}\n"
        "Restart=always\nRestartSec=5\n\n"
        "[Install]\nWantedBy=default.target\n"
    ).encode()


def _plan(config: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], bytes]:
    executable = shutil.which(str(config["lark_cli_bin"]))
    argv = _collector_argv(config, executable or str(config["lark_cli_bin"]))
    service_payload = _service_payload(config, argv)
    return (
        {
            "ok": True,
            "schema_version": PLAN_SCHEMA_VERSION,
            "enabled": config["enabled"],
            "status": "install_ready" if executable else "dependency_missing",
            "service_name": config["service_name"],
            "supervisor": config["supervisor"],
            "event_key": config["event_key"],
            "identity": config["identity"],
            "profile_bound": bool(config.get("profile")),
            "profile_source": config["profile_source"],
            "profile_returned": False,
            "capture_scope": config["inbox"]["capture_scope"],
            "thread_complete": config["inbox"]["thread_complete"],
            "lark_cli_available": executable is not None,
            "install_hint": (
                None
                if executable
                else "Install and configure lark-cli, then rerun the collector plan."
            ),
            "service_digest": hashlib.sha256(service_payload).hexdigest()[:16],
            "local_paths_returned": False,
            "chat_id_returned": False,
            "credentials_returned": False,
            "external_writes_performed": False,
        },
        argv,
        service_payload,
    )


def plan_lark_event_collector(
    *, project: str | Path, config_path: str | Path
) -> dict[str, Any]:
    config = load_lark_event_collector_config(project=project, config_path=config_path)
    plan, _, _ = _plan(config)
    return plan


def _run(runner: Runner, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return runner(list(argv), capture_output=True, text=True, check=False)


def _event_consume_available(runner: Runner, executable: str) -> bool:
    support = _run(
        runner,
        [*_executable_prefix(executable), "event", "consume", "--help"],
    )
    return support.returncode == 0


def install_lark_event_collector(
    *,
    project: str | Path,
    config_path: str | Path,
    execute: bool = False,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    config = load_lark_event_collector_config(project=project, config_path=config_path)
    plan, _, _ = _plan(config)
    if not config["enabled"]:
        raise ValueError("cannot install a disabled lark collector")
    if not plan["lark_cli_available"]:
        return {**plan, "schema_version": INSTALL_SCHEMA_VERSION, "execute": execute}
    executable = shutil.which(str(config["lark_cli_bin"]))
    if not _event_consume_available(runner, str(executable)):
        return {
            **plan,
            "schema_version": INSTALL_SCHEMA_VERSION,
            "ok": False,
            "status": "dependency_incompatible",
            "execute": execute,
            "install_hint": "Upgrade lark-cli to a version with event consume support.",
        }
    argv = _collector_argv(config, str(executable))
    service_payload = _service_payload(config, argv)
    if not execute:
        return {
            **plan,
            "schema_version": INSTALL_SCHEMA_VERSION,
            "status": "preview_ready",
            "execute": False,
            "would_write_service": True,
        }
    service_path = _service_file(config)
    service_path.parent.mkdir(parents=True, exist_ok=True)
    (Path(config["project"]) / ".loopx" / "runtime" / "lark-collector").mkdir(
        parents=True, exist_ok=True
    )
    temporary = service_path.with_suffix(service_path.suffix + ".tmp")
    temporary.write_bytes(service_payload)
    temporary.replace(service_path)
    if config["supervisor"] == "launchd":
        domain = f"gui/{os.getuid()}"
        _run(runner, ["launchctl", "bootout", f"{domain}/{config['service_name']}"])
        started = _run(runner, ["launchctl", "bootstrap", domain, str(service_path)])
        if started.returncode == 0:
            started = _run(
                runner,
                ["launchctl", "kickstart", "-k", f"{domain}/{config['service_name']}"],
            )
    else:
        reloaded = _run(runner, ["systemctl", "--user", "daemon-reload"])
        started = (
            _run(
                runner,
                ["systemctl", "--user", "enable", "--now", str(config["service_name"])],
            )
            if reloaded.returncode == 0
            else reloaded
        )
    return {
        **plan,
        "schema_version": INSTALL_SCHEMA_VERSION,
        "status": "installed" if started.returncode == 0 else "supervisor_start_failed",
        "ok": started.returncode == 0,
        "execute": True,
        "write_performed": True,
        "supervisor_start_performed": True,
        "supervisor_start_succeeded": started.returncode == 0,
    }


def inspect_lark_event_collector(
    *,
    project: str | Path,
    config_path: str | Path,
    probe_event_bus: bool = False,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    config = load_lark_event_collector_config(project=project, config_path=config_path)
    plan, _, _ = _plan(config)
    service_path = _service_file(config)
    if config["supervisor"] == "launchd":
        observed = _run(
            runner,
            ["launchctl", "print", f"gui/{os.getuid()}/{config['service_name']}"],
        )
    else:
        observed = _run(
            runner,
            ["systemctl", "--user", "is-active", str(config["service_name"])],
        )
    bus_healthy = None
    if probe_event_bus and plan["lark_cli_available"]:
        executable = shutil.which(str(config["lark_cli_bin"]))
        profile_args = (
            ["--profile", str(config["profile"])] if config.get("profile") else []
        )
        bus = _run(
            runner,
            [
                str(executable),
                *profile_args,
                "event",
                "status",
                "--json",
                "--fail-on-orphan",
            ],
        )
        bus_healthy = bus.returncode == 0
    inbox_status = inspect_lark_event_inbox(
        project=config["project"],
        config_path=config["event_inbox_config_ref"],
        limit=1,
    )
    event_count = int(inbox_status.get("captured_count") or 0)
    active = observed.returncode == 0 and (
        config["supervisor"] != "launchd" or "state = running" in observed.stdout
    )
    installed = service_path.is_file()
    healthy = bool(
        config["enabled"]
        and plan["lark_cli_available"]
        and installed
        and active
        and (bus_healthy is not False)
    )
    return {
        "ok": True,
        "schema_version": STATUS_SCHEMA_VERSION,
        "enabled": config["enabled"],
        "status": "healthy" if healthy else "attention_required",
        "healthy": healthy,
        "service_name": config["service_name"],
        "supervisor": config["supervisor"],
        "profile_bound": bool(config.get("profile")),
        "profile_source": config["profile_source"],
        "profile_returned": False,
        "installed": installed,
        "active": active,
        "lark_cli_available": plan["lark_cli_available"],
        "event_bus_probe_performed": probe_event_bus,
        "event_bus_healthy": bus_healthy,
        "captured_event_count": event_count,
        "real_event_evidence_present": event_count > 0,
        "thread_complete": config["inbox"]["thread_complete"],
        "local_paths_returned": False,
        "chat_id_returned": False,
        "credentials_returned": False,
        "external_writes_performed": False,
    }
