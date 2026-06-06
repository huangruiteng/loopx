from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .heartbeat_prompt import build_heartbeat_prompt
from .history import load_registry
from .paths import DEFAULT_RUNTIME_ROOT, global_registry_path, resolve_runtime_root
from .registry import registry_goals, resolve_state_file


DEFAULT_UPGRADE_MODES = ("thin",)


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_summary(prompt: dict[str, Any], mode: str) -> dict[str, Any]:
    task_body = str(prompt.get("task_body") or "")
    if mode == "full":
        command = prompt.get("expanded_prompt_command")
    else:
        command = prompt.get(f"{mode}_prompt_command")
    return {
        "mode": mode,
        "sha256": prompt_digest(task_body),
        "char_count": len(task_body),
        "line_count": len(task_body.splitlines()),
        "command": command,
    }


def load_installed_manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "available": False,
            "path": None,
            "entries": [],
            "reason": "no installed automation manifest provided",
        }
    if not path.exists():
        return {
            "available": False,
            "path": str(path),
            "entries": [],
            "reason": "installed automation manifest does not exist",
        }
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        entries = raw
    elif isinstance(raw, dict):
        entries = raw.get("automations") or raw.get("entries") or []
    else:
        entries = []
    return {
        "available": True,
        "path": str(path),
        "entries": [entry for entry in entries if isinstance(entry, dict)],
    }


def installed_entry_digest(entry: dict[str, Any]) -> str | None:
    for key in ("prompt_sha256", "task_body_sha256", "sha256"):
        value = entry.get(key)
        if value:
            return str(value)
    task_body = entry.get("task_body")
    if isinstance(task_body, str):
        return prompt_digest(task_body)
    return None


def entry_declares_not_installed(entry: dict[str, Any] | None) -> bool:
    if not entry:
        return False
    status = str(entry.get("status") or "").replace("-", "_").lower()
    if status in {"not_installed", "no_automation", "uninstalled"}:
        return True
    installed = entry.get("installed")
    return installed is False


def entry_key(entry: dict[str, Any]) -> tuple[str, str]:
    return str(entry.get("goal_id") or ""), str(entry.get("mode") or DEFAULT_UPGRADE_MODES[0])


def index_installed_entries(entries: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        goal_id, mode = entry_key(entry)
        if goal_id:
            indexed[(goal_id, mode)] = entry
    return indexed


def build_upgrade_plan(
    *,
    registry_path: Path,
    runtime_root_override: str | None = None,
    installed_manifest: Path | None = None,
    cli_bin: str = "goal-harness",
    modes: list[str] | tuple[str, ...] | None = None,
    goal_ids: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    if not registry_path.exists():
        fallback = global_registry_path(runtime_root or DEFAULT_RUNTIME_ROOT)
        if fallback.exists():
            registry_path = fallback
            registry = load_registry(registry_path)
            runtime_root = resolve_runtime_root(registry, runtime_root_override)

    selected_modes = tuple(modes or DEFAULT_UPGRADE_MODES)
    selected_goal_ids = set(goal_ids or [])
    manifest = load_installed_manifest(installed_manifest)
    installed_by_key = index_installed_entries(manifest["entries"])
    managed: list[dict[str, Any]] = []

    for goal in registry_goals(registry):
        goal_id = str(goal.get("id") or "")
        if selected_goal_ids and goal_id not in selected_goal_ids:
            continue
        repo = Path(str(goal.get("repo") or ".")).expanduser()
        state_file = resolve_state_file(repo, goal.get("state_file"))
        prompt_summaries: dict[str, dict[str, Any]] = {}
        installed: dict[str, dict[str, Any]] = {}
        for mode in selected_modes:
            prompt = build_heartbeat_prompt(
                goal_id=goal_id,
                active_state=None,
                active_state_source="registry",
                resolved_active_state=state_file,
                compact=mode == "compact",
                brief=mode == "brief",
                thin=mode == "thin",
                cli_bin=cli_bin,
            )
            summary = prompt_summary(prompt, mode)
            prompt_summaries[mode] = summary
            entry = installed_by_key.get((goal_id, mode))
            expected_digest = str(summary.get("sha256") or "")
            not_installed = entry_declares_not_installed(entry)
            actual_digest = None if not_installed else installed_entry_digest(entry) if entry else None
            status = "unknown"
            if not_installed:
                status = "not_installed"
            elif entry:
                status = "current" if actual_digest == expected_digest else "stale"
            installed[mode] = {
                "status": status,
                "requires_update": status in {"unknown", "stale"},
                "automation_id": entry.get("automation_id") if entry else None,
                "installed": False if not_installed else bool(entry),
                "prompt_sha256": actual_digest,
                "expected_sha256": expected_digest,
            }

        managed.append(
            {
                "goal_id": goal_id,
                "adapter_kind": (goal.get("adapter") or {}).get("kind") if isinstance(goal.get("adapter"), dict) else None,
                "adapter_status": (goal.get("adapter") or {}).get("status") if isinstance(goal.get("adapter"), dict) else None,
                "repo": str(repo),
                "state_file": str(state_file) if state_file else None,
                "state_file_exists": bool(state_file and state_file.exists()),
                "generated_prompts": prompt_summaries,
                "installed_prompts": installed,
                "requires_update": any(item["requires_update"] for item in installed.values()),
            }
        )

    unknown = sum(
        1
        for goal in managed
        for installed in goal["installed_prompts"].values()
        if installed["status"] == "unknown"
    )
    stale = sum(
        1
        for goal in managed
        for installed in goal["installed_prompts"].values()
        if installed["status"] == "stale"
    )
    current = sum(
        1
        for goal in managed
        for installed in goal["installed_prompts"].values()
        if installed["status"] == "current"
    )
    not_installed = sum(
        1
        for goal in managed
        for installed in goal["installed_prompts"].values()
        if installed["status"] == "not_installed"
    )
    ready = bool(managed) and unknown == 0 and stale == 0
    return {
        "ok": True,
        "mode": "upgrade-plan",
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "cli_bin": cli_bin,
        "prompt_modes": list(selected_modes),
        "installed_manifest": manifest,
        "summary": {
            "managed_goal_count": len(managed),
            "current_prompt_count": current,
            "stale_prompt_count": stale,
            "unknown_prompt_count": unknown,
            "not_installed_prompt_count": not_installed,
            "ready_for_default_promotion": ready,
        },
        "managed_heartbeats": managed,
        "recommended_action": "promotion propagation is complete"
        if ready
        else "refresh installed heartbeat automations/controller clients before default promotion",
    }


def render_upgrade_plan_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Goal Harness Upgrade Plan",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- cli_bin: `{payload.get('cli_bin')}`",
        f"- prompt_modes: `{', '.join(payload.get('prompt_modes') or [])}`",
        f"- ready_for_default_promotion: `{summary.get('ready_for_default_promotion')}`",
        f"- managed_goal_count: `{summary.get('managed_goal_count')}`",
        f"- current_prompt_count: `{summary.get('current_prompt_count')}`",
        f"- stale_prompt_count: `{summary.get('stale_prompt_count')}`",
        f"- unknown_prompt_count: `{summary.get('unknown_prompt_count')}`",
        f"- not_installed_prompt_count: `{summary.get('not_installed_prompt_count')}`",
        f"- recommended_action: `{payload.get('recommended_action')}`",
    ]
    manifest = payload.get("installed_manifest") if isinstance(payload.get("installed_manifest"), dict) else {}
    lines.extend(
        [
            "",
            "## Installed Manifest",
            "",
            f"- available: `{manifest.get('available')}`",
            f"- path: `{manifest.get('path')}`",
            f"- reason: `{manifest.get('reason')}`",
        ]
    )
    lines.extend(["", "## Managed Heartbeats", ""])
    for goal in payload.get("managed_heartbeats") or []:
        installed = goal.get("installed_prompts") if isinstance(goal.get("installed_prompts"), dict) else {}
        generated = goal.get("generated_prompts") if isinstance(goal.get("generated_prompts"), dict) else {}
        status_parts = []
        for mode, status in installed.items():
            if isinstance(status, dict):
                status_parts.append(f"{mode}={status.get('status')}")
        prompt_parts = []
        for mode, prompt in generated.items():
            if isinstance(prompt, dict):
                prompt_parts.append(
                    f"{mode}:sha={str(prompt.get('sha256') or '')[:12]} chars={prompt.get('char_count')}"
                )
        lines.extend(
            [
                f"- `{goal.get('goal_id')}` state_file_exists=`{goal.get('state_file_exists')}` "
                f"requires_update=`{goal.get('requires_update')}` installed=`{', '.join(status_parts)}`",
                f"  prompts: `{'; '.join(prompt_parts)}`",
            ]
        )
    return "\n".join(lines) + "\n"
