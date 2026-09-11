"""Read scoped Core evidence from an operator-configured SSH source."""

import json
import re
import shlex
import subprocess

from . import POLICY_SCHEMA, _root, _read, _write
from ...file_lock import exclusive_file_lock
from ...control_plane.status.ssh_host_catalog import configured_ssh_host_aliases


def grants(root, channel):
    try:
        policy = _read(_root(root) / "policy.json")
        if policy.get("schema_version") != POLICY_SCHEMA:
            return {}
        raw = policy.get("sources", {}).get(channel, {}).get("evidence_ssh_hosts", {})
        return {
            h: sorted(set(ids))
            for h, ids in raw.items()
            if isinstance(h, str)
            and isinstance(ids, list)
            and ids
            and len(ids) <= 128
            and all(
                isinstance(g, str)
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", g)
                for g in ids
            )
        }
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def configure(root, *, channel, host, goal_ids, execute=False, config_path=None):
    if not re.fullmatch(r"manager\.external\.[a-f0-9]{24}", channel):
        raise ValueError("exact external manager channel required")
    if host not in configured_ssh_host_aliases(config_path):
        raise ValueError("host must be an existing SSH alias")
    if len(goal_ids) > 128 or any(
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", g) for g in goal_ids
    ):
        raise ValueError("bounded exact remote Goal IDs required")
    ids = sorted(set(goal_ids))
    if execute:
        path = _root(root) / "policy.json"
        with exclusive_file_lock(path.with_suffix(".lock")):
            policy = (
                _read(path)
                if path.exists()
                else {"schema_version": POLICY_SCHEMA, "sources": {}}
            )
            if policy.get("schema_version") != POLICY_SCHEMA:
                raise ValueError("invalid manager policy")
            sources = (
                policy.setdefault("sources", {})
                .setdefault(channel, {})
                .setdefault("evidence_ssh_hosts", {})
            )
            if ids:
                sources[host] = ids
            else:
                sources.pop(host, None)
            _write(path, policy)
    return {
        "ok": True,
        "executed": execute,
        "source_id": "ssh:" + host,
        "goal_ids": ids,
        "scope": "audience_remote_goal_summaries",
    }


def sources(root, channel, owner, config_path=None):
    allowed = grants(root, channel)
    return [{"source_id": "local", "source_host": "local", "status": "available"}] + [
        {
            "source_id": "ssh:" + h,
            "source_host": h,
            "status": "not_read",
            "scope": "remote_registry" if owner else "explicit_goal_grant",
        }
        for h in configured_ssh_host_aliases(config_path)
        if owner or h in allowed
    ]


def read_remote(
    root, channel, owner, args, scope_valid, *, runner=subprocess.run, config_path=None
):
    host = args["source_id"].removeprefix("ssh:")
    before = grants(root, channel)
    if (
        not scope_valid()
        or host not in configured_ssh_host_aliases(config_path)
        or (not owner and host not in before)
    ):
        return {"ok": False, "error": "source_outside_available_scope"}
    goal = args.get("goal_id")
    if goal and not owner and goal not in before[host]:
        return {"ok": False, "error": "goal_outside_available_scope"}
    # Values are validated/quoted; the model cannot choose a binary, path or command.
    argv = [
        "goal-portfolio",
        "--manager-view",
        args["view"],
        "--offset",
        str(args.get("offset", 0)),
        "--limit",
        str(args.get("limit", 8)),
        "--days",
        str(args.get("days", 1)),
    ]
    for gid in ([goal] if goal else (None if owner else before[host])) or []:
        argv += ["--goal-id", gid]
    if args.get("include_stopped"):
        argv += ["--include-stopped"]
    command = (
        'exec "$HOME/.local/bin/loopx" --registry "$HOME/.codex/loopx/registry.global.json" --runtime-root "$HOME/.codex/loopx" --format json '
        + shlex.join(argv)
    )
    ssh = [
        "ssh",
        "-T",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "ForwardX11=no",
    ]
    if config_path:
        ssh += ["-F", str(config_path)]
    try:
        result = runner(
            [*ssh, host, command], capture_output=True, text=True, timeout=45
        )
        if result.returncode or len(result.stdout) > 100000:
            raise ValueError("remote read unavailable")
        packet = json.loads(result.stdout)
        if (
            not isinstance(packet, dict)
            or packet.get("schema_version") != "manager_evidence_page_v1"
            or not isinstance(packet.get("rows"), list)
            or any(not isinstance(r, dict) for r in packet["rows"])
        ):
            raise ValueError("remote protocol unavailable")
        if (
            not scope_valid()
            or (not owner and before != grants(root, channel))
            or host not in configured_ssh_host_aliases(config_path)
        ):
            return {"ok": False, "error": "authorization_changed"}
        if not owner and any(
            r.get("goal_id") not in before[host] for r in packet["rows"]
        ):
            return {"ok": False, "error": "remote_scope_mismatch"}
        packet.update(source_id=args["source_id"], source_host=host)
        packet["rows"] = [
            {**r, "source_id": args["source_id"], "source_host": host}
            for r in packet["rows"]
        ]
        return packet
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return {
            "ok": False,
            "source_id": args["source_id"],
            "error": "remote_evidence_unavailable_or_upgrade_required",
            "coverage": {"discovered": None, "complete": False},
            "rows": [],
        }
