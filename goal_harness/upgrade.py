from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .heartbeat_prompt import build_heartbeat_prompt
from .history import load_registry
from .paths import DEFAULT_RUNTIME_ROOT, global_registry_path, resolve_runtime_root
from .registry import registry_goals, resolve_state_file


DEFAULT_UPGRADE_MODES = ("thin",)
STAGE_DEFERRED_ATTENTION_STATUSES = {
    "stage_deferred_not_installed",
}
STAGE_DEFERRED_ADAPTER_STATUSES = {
    "planned",
}


def prompt_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_summary(prompt: dict[str, Any], mode: str) -> dict[str, Any]:
    task_body = str(prompt.get("task_body") or "")
    if mode == "full":
        command = prompt.get("expanded_prompt_command")
    else:
        command = prompt.get(f"{mode}_prompt_command")
    interface_budget = prompt.get("interface_budget") if isinstance(prompt.get("interface_budget"), dict) else {}
    return {
        "mode": mode,
        "sha256": prompt_digest(task_body),
        "char_count": len(task_body),
        "line_count": len(task_body.splitlines()),
        "interface_budget": interface_budget,
        "within_interface_budget": interface_budget.get("within_budget"),
        "interface_budget_char_count": interface_budget.get("budget_char_count"),
        "interface_budget_max_chars": interface_budget.get("max_chars"),
        "command": command,
    }


def load_installed_manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        return load_codex_app_automation_manifest()
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


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()


def parse_automation_toml(path: Path) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if value.startswith('"') and value.endswith('"'):
            try:
                values[key] = json.loads(value)
            except json.JSONDecodeError:
                values[key] = value[1:-1]
        elif value in {"true", "false"}:
            values[key] = value == "true"
        else:
            try:
                values[key] = int(value)
            except ValueError:
                values[key] = value
    return values


def infer_goal_id_from_prompt(prompt: str) -> str | None:
    patterns = (
        r"Advance\s+`([^`]+)`\s+from\b",
        r"Advance\s+`([^`]+)`\s+using\b",
        r"--goal-id\s+([A-Za-z0-9_.:-]+)",
        r"goal_id:\s*`([^`]+)`",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            return match.group(1)
    return None


def infer_prompt_mode(prompt: str) -> str:
    if "compact Goal Harness heartbeat body" in prompt:
        return "compact"
    if "Brief installed Goal Harness heartbeat" in prompt:
        return "brief"
    if "Keep the heartbeat thin." in prompt or "from the registry-declared active state" in prompt:
        return "thin"
    return DEFAULT_UPGRADE_MODES[0]


def load_codex_app_automation_manifest(root: Path | None = None) -> dict[str, Any]:
    home = root or codex_home()
    automations_root = home / "automations"
    if not automations_root.exists():
        return {
            "available": False,
            "path": str(automations_root),
            "entries": [],
            "reason": "no installed automation manifest provided and Codex App automations directory does not exist",
            "source": "codex_app_automations",
        }

    entries: list[dict[str, Any]] = []
    for path in sorted(automations_root.glob("*/automation.toml")):
        try:
            automation = parse_automation_toml(path)
        except OSError:
            continue
        if automation.get("kind") != "heartbeat":
            continue
        prompt = automation.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            continue
        goal_id = infer_goal_id_from_prompt(prompt)
        if not goal_id:
            continue
        status = str(automation.get("status") or "ACTIVE")
        entries.append(
            {
                "automation_id": str(automation.get("id") or path.parent.name),
                "goal_id": goal_id,
                "mode": infer_prompt_mode(prompt),
                "prompt_sha256": prompt_digest(prompt),
                "char_count": len(prompt),
                "line_count": len(prompt.splitlines()),
                "status": status,
                "installed": status.upper() != "DELETED",
                "source": "codex_app_automation_toml",
                "path": str(path),
            }
        )

    return {
        "available": True,
        "path": str(automations_root),
        "entries": entries,
        "source": "codex_app_automations",
        "reason": None if entries else "no Goal Harness heartbeat automations discovered",
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


def goal_adapter(goal: dict[str, Any]) -> dict[str, Any]:
    adapter = goal.get("adapter")
    return adapter if isinstance(adapter, dict) else {}


def goal_adapter_status(goal: dict[str, Any]) -> str:
    return str(goal_adapter(goal).get("status") or "")


def goal_adapter_kind(goal: dict[str, Any]) -> str | None:
    kind = goal_adapter(goal).get("kind")
    return str(kind) if kind else None


def goal_is_stage_deferred(goal: dict[str, Any]) -> bool:
    attention_status = str(goal.get("attention_status") or "").replace("-", "_").lower()
    if attention_status in STAGE_DEFERRED_ATTENTION_STATUSES:
        return True
    adapter_status = goal_adapter_status(goal).replace("-", "_").lower()
    return adapter_status in STAGE_DEFERRED_ADAPTER_STATUSES


def stage_deferred_goal_summary(goal: dict[str, Any], state_file: Path | None) -> dict[str, Any]:
    return {
        "goal_id": str(goal.get("id") or ""),
        "adapter_kind": goal_adapter_kind(goal),
        "adapter_status": goal_adapter_status(goal) or None,
        "status": goal.get("status"),
        "attention_status": goal.get("attention_status"),
        "repo": str(Path(str(goal.get("repo") or ".")).expanduser()),
        "state_file": str(state_file) if state_file else None,
        "state_file_exists": bool(state_file and state_file.exists()),
        "requires_update": False,
        "deferred_reason": "stage_deferred_until_operator_authorizes_heartbeat",
        "recommended_action": goal.get("recommended_action")
        or "do not install or update this heartbeat until the operator authorizes the stage",
    }


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
    manifest_entries = manifest["entries"]
    manifest_task_body_count = sum(1 for entry in manifest_entries if isinstance(entry, dict) and "task_body" in entry)
    installed_by_key = index_installed_entries(manifest["entries"])
    managed: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    for goal in registry_goals(registry):
        goal_id = str(goal.get("id") or "")
        if selected_goal_ids and goal_id not in selected_goal_ids:
            continue
        repo = Path(str(goal.get("repo") or ".")).expanduser()
        state_file = resolve_state_file(repo, goal.get("state_file"))
        if goal_is_stage_deferred(goal):
            deferred.append(stage_deferred_goal_summary(goal, state_file))
            continue
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
                "adapter_kind": goal_adapter_kind(goal),
                "adapter_status": goal_adapter_status(goal) or None,
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
    if ready:
        recommended_action = "promotion propagation is complete"
    elif managed:
        recommended_action = "refresh installed heartbeat automations/controller clients before default promotion"
    elif deferred:
        recommended_action = "selected heartbeats are stage-deferred; do not install until the operator authorizes that stage"
    else:
        recommended_action = "no registry-managed heartbeats matched the upgrade plan selection"
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
            "stage_deferred_goal_count": len(deferred),
            "ready_for_default_promotion": ready,
            "installed_manifest_available": manifest.get("available"),
            "installed_manifest_source": manifest.get("source"),
            "installed_manifest_entry_count": len(manifest_entries),
            "installed_manifest_task_body_count": manifest_task_body_count,
            "installed_manifest_has_task_body": manifest_task_body_count > 0,
        },
        "managed_heartbeats": managed,
        "stage_deferred_heartbeats": deferred,
        "recommended_action": recommended_action,
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
        f"- stage_deferred_goal_count: `{summary.get('stage_deferred_goal_count')}`",
        f"- installed_manifest_source: `{summary.get('installed_manifest_source')}`",
        f"- installed_manifest_entry_count: `{summary.get('installed_manifest_entry_count')}`",
        f"- installed_manifest_has_task_body: `{summary.get('installed_manifest_has_task_body')}`",
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
    deferred = payload.get("stage_deferred_heartbeats") or []
    if deferred:
        lines.extend(["", "## Stage Deferred Heartbeats", ""])
        for goal in deferred:
            if not isinstance(goal, dict):
                continue
            lines.append(
                f"- `{goal.get('goal_id')}` adapter=`{goal.get('adapter_kind')}:{goal.get('adapter_status')}` "
                f"attention_status=`{goal.get('attention_status')}` requires_update=`{goal.get('requires_update')}`"
            )
    return "\n".join(lines) + "\n"
