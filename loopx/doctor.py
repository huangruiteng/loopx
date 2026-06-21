from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .paths import DEFAULT_RUNTIME_ROOT


PROMOTION_READINESS_CLASSIFICATIONS = {
    "canary_promotion_readiness_smoke_group",
}
PROMOTION_READINESS_FRESHNESS_HOURS = 24
REQUIRED_INSTALLED_SKILL_PHRASES = {
    "loopx-project": (
        "--classification <PUBLIC_SAFE_PROGRESS_CLASSIFICATION>",
        "--delivery-batch-scale multi_surface",
        "--delivery-outcome outcome_progress",
    ),
    "loopx-doc-registry": (
        "Use even when the user does not mention LoopX or doc registry",
        "use `.loopx/registry.json` as the project-local doc registry",
        "not a substitute for project-local authority registration",
    ),
    "loopx-self-repair": (
        "Build a compact evidence packet",
        "references/repair-patterns.md",
        "Repair at the lowest durable layer",
    ),
}


def user_local_bin() -> Path:
    return Path.home() / ".local" / "bin"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()


def command_release_root(command_realpath: Path | None) -> Path | None:
    if (
        command_realpath
        and command_realpath.name == "loopx"
        and command_realpath.parent.name == "scripts"
    ):
        return command_realpath.parent.parent
    return None


def resolve_command_path(name: str) -> Path | None:
    path_text = shutil.which(name)
    return Path(path_text).expanduser() if path_text else None


def is_release_snapshot(root: Path | None) -> bool:
    return bool(root and "releases" in root.parts)


def command_root_summary(command_path: Path | None, command_realpath: Path | None) -> dict[str, Any]:
    root = command_release_root(command_realpath)
    return {
        "command": str(command_path) if command_path else None,
        "realpath": str(command_realpath) if command_realpath else None,
        "root": str(root) if root else None,
        "release_id": root.name if is_release_snapshot(root) else None,
        "is_release_snapshot": is_release_snapshot(root),
    }


def parse_event_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def add_promotion_readiness_freshness(
    event: dict[str, Any],
    *,
    now: datetime | None = None,
    freshness_hours: int = PROMOTION_READINESS_FRESHNESS_HOURS,
) -> dict[str, Any]:
    result = dict(event)
    result["freshness_window_hours"] = freshness_hours
    if not result.get("available"):
        result.update(
            {
                "freshness_status": "missing",
                "is_fresh": False,
                "requires_readiness_run": True,
                "age_seconds": None,
                "age_hours": None,
            }
        )
        return result

    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    generated_at = parse_event_time(result.get("generated_at"))
    if generated_at is None:
        result.update(
            {
                "freshness_status": "unknown",
                "is_fresh": False,
                "requires_readiness_run": True,
                "age_seconds": None,
                "age_hours": None,
            }
        )
        return result

    age_seconds = max(0, int((reference - generated_at).total_seconds()))
    is_fresh = age_seconds <= freshness_hours * 3600
    result.update(
        {
            "freshness_status": "fresh" if is_fresh else "stale",
            "is_fresh": is_fresh,
            "requires_readiness_run": not is_fresh,
            "age_seconds": age_seconds,
            "age_hours": round(age_seconds / 3600, 2),
            "freshness_reference_time": reference.isoformat(),
        }
    )
    return result


def skill_has_delivery_hints(skill_path: Path) -> bool:
    if not skill_path.exists():
        return False
    text = " ".join(skill_path.read_text(encoding="utf-8").split())
    return all(phrase in text for phrase in REQUIRED_INSTALLED_SKILL_PHRASES["loopx-project"])


def skill_has_required_phrases(skill_path: Path, phrases: tuple[str, ...]) -> bool:
    if not skill_path.exists():
        return False
    text = " ".join(skill_path.read_text(encoding="utf-8").split())
    return all(phrase in text for phrase in phrases)


def installed_skill_summary(skills_root: Path) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for skill_name, phrases in REQUIRED_INSTALLED_SKILL_PHRASES.items():
        skill_path = skills_root / skill_name / "SKILL.md"
        summaries[skill_name] = {
            "path": str(skill_path),
            "exists": skill_path.exists(),
            "required_phrases": skill_has_required_phrases(skill_path, phrases),
        }
    return summaries


def latest_promotion_readiness_event(runtime_root: Path) -> dict[str, Any]:
    goals_dir = runtime_root / "goals"
    if not goals_dir.exists():
        return {
            "available": False,
            "runtime_root": str(runtime_root),
            "reason": "runtime goals directory does not exist",
        }

    matches: list[dict[str, Any]] = []
    for index_path in goals_dir.glob("*/runs/index.jsonl"):
        goal_id = index_path.parent.parent.name
        try:
            lines = index_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            classification = str(item.get("classification") or "")
            if classification not in PROMOTION_READINESS_CLASSIFICATIONS:
                continue
            json_path = Path(str(item.get("json_path") or ""))
            markdown_path = Path(str(item.get("markdown_path") or ""))
            matches.append(
                {
                    "available": True,
                    "goal_id": str(item.get("goal_id") or goal_id),
                    "generated_at": item.get("generated_at"),
                    "classification": classification,
                    "delivery_batch_scale": item.get("delivery_batch_scale"),
                    "delivery_outcome": item.get("delivery_outcome"),
                    "recommended_action": item.get("recommended_action"),
                    "json_exists": json_path.exists() if str(json_path) else False,
                    "markdown_exists": markdown_path.exists() if str(markdown_path) else False,
                }
            )

    if not matches:
        return {
            "available": False,
            "runtime_root": str(runtime_root),
            "reason": "no canary promotion readiness run found",
        }
    matches.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    latest = matches[0]
    latest["runtime_root"] = str(runtime_root)
    return latest


def collect_doctor() -> dict[str, Any]:
    loopx_path = resolve_command_path("loopx")
    loopx_canary_path = resolve_command_path("loopx-canary")
    command_path_primary = loopx_path
    canary_path = loopx_canary_path
    command_path = command_path_primary
    command_realpath = command_path.resolve() if command_path else None
    canary_realpath = canary_path.resolve() if canary_path else None
    loopx_realpath = loopx_path.resolve() if loopx_path else None
    loopx_canary_realpath = loopx_canary_path.resolve() if loopx_canary_path else None
    module_path = Path(__file__).resolve()
    package_dir = module_path.parent
    repo_root = package_dir.parent
    install_script = repo_root / "scripts" / "install-local.sh"
    wrapper_script = repo_root / "scripts" / "loopx"
    release_root = command_release_root(command_realpath)
    canary_root = command_release_root(canary_realpath)
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    local_bin = user_local_bin()
    skills_root = codex_home() / "skills"
    skill_path = skills_root / "loopx-project" / "SKILL.md"
    skills = installed_skill_summary(skills_root)
    release_provenance = {
        "runtime_root": str(DEFAULT_RUNTIME_ROOT),
        "default_release": command_root_summary(command_path, command_realpath),
        "live_canary": {
            **command_root_summary(canary_path, canary_realpath),
            "separate_from_default": bool(canary_realpath and command_realpath and canary_realpath != command_realpath),
        },
        "current_invocation": {
            "module_path": str(module_path),
            "repo_root": str(repo_root),
            "source": "release_snapshot" if is_release_snapshot(repo_root) else "live_checkout",
        },
        "promotion_readiness": add_promotion_readiness_freshness(
            latest_promotion_readiness_event(DEFAULT_RUNTIME_ROOT)
        ),
    }
    checks = [
        {
            "id": "command_on_path",
            "required": True,
            "ok": command_path is not None,
            "detail": str(command_path) if command_path else "loopx was not found on PATH",
        },
        {
            "id": "command_resolves",
            "required": True,
            "ok": bool(command_realpath and command_realpath.exists()),
            "detail": str(command_realpath) if command_realpath else "no command realpath",
        },
        {
            "id": "default_command_is_release_snapshot",
            "required": False,
            "ok": bool(release_root and "releases" in release_root.parts),
            "detail": str(release_root) if release_root else "default command is not a release snapshot",
        },
        {
            "id": "canary_command_on_path",
            "required": False,
            "ok": canary_path is not None,
            "detail": str(canary_path) if canary_path else "loopx-canary was not found on PATH",
        },
        {
            "id": "canary_separate_from_default",
            "required": False,
            "ok": bool(canary_realpath and command_realpath and canary_realpath != command_realpath),
            "detail": str(canary_realpath) if canary_realpath else "no canary realpath",
        },
        {
            "id": "module_importable",
            "required": True,
            "ok": module_path.exists(),
            "detail": str(module_path),
        },
        {
            "id": "install_script_exists",
            "required": False,
            "ok": install_script.exists(),
            "detail": str(install_script),
        },
        {
            "id": "wrapper_script_exists",
            "required": False,
            "ok": wrapper_script.exists(),
            "detail": str(wrapper_script),
        },
        {
            "id": "local_bin_on_path",
            "required": False,
            "ok": str(local_bin) in path_entries,
            "detail": str(local_bin),
        },
        {
            "id": "installed_skill_exists",
            "required": False,
            "ok": skill_path.exists(),
            "detail": str(skill_path),
        },
        {
            "id": "installed_skill_delivery_hints",
            "required": False,
            "ok": skill_has_delivery_hints(skill_path),
            "detail": str(skill_path),
        },
        {
            "id": "installed_required_skills",
            "required": False,
            "ok": all(skill.get("exists") for skill in skills.values()),
            "detail": ",".join(sorted(skills)),
        },
        {
            "id": "installed_required_skill_routes",
            "required": False,
            "ok": all(skill.get("required_phrases") for skill in skills.values()),
            "detail": ",".join(
                f"{name}={skill.get('required_phrases')}" for name, skill in sorted(skills.items())
            ),
        },
    ]
    return {
        "ok": all(check["ok"] for check in checks if check["required"]),
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "path": {
            "loopx": str(loopx_path) if loopx_path else None,
            "loopx_realpath": str(loopx_realpath) if loopx_realpath else None,
            "loopx_canary": str(loopx_canary_path) if loopx_canary_path else None,
            "loopx_canary_realpath": str(loopx_canary_realpath) if loopx_canary_realpath else None,
            "user_local_bin": str(local_bin),
            "user_local_bin_on_path": str(local_bin) in path_entries,
        },
        "package": {
            "module_path": str(module_path),
            "repo_root": str(repo_root),
            "release_root": str(release_root) if release_root else None,
            "canary_root": str(canary_root) if canary_root else None,
            "install_script": str(install_script),
            "wrapper_script": str(wrapper_script),
        },
        "release_provenance": release_provenance,
        "skill": {
            "path": str(skill_path),
            "exists": skill_path.exists(),
            "delivery_hints": skill_has_delivery_hints(skill_path),
        },
        "skills": skills,
        "checks": checks,
        "fix": f"Run `{repo_root / 'scripts' / 'install-local.sh'}` and start a new shell, or export PATH=\"{local_bin}:$PATH\".",
    }


def render_doctor_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Doctor",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- loopx: `{(payload.get('path') or {}).get('loopx')}`",
        f"- loopx_realpath: `{(payload.get('path') or {}).get('loopx_realpath')}`",
        f"- loopx_canary: `{(payload.get('path') or {}).get('loopx_canary')}`",
        f"- loopx_canary_realpath: `{(payload.get('path') or {}).get('loopx_canary_realpath')}`",
        f"- release_root: `{(payload.get('package') or {}).get('release_root')}`",
        f"- canary_root: `{(payload.get('package') or {}).get('canary_root')}`",
        f"- installed_skill: `{(payload.get('skill') or {}).get('path')}`",
        f"- installed_skill_delivery_hints: `{(payload.get('skill') or {}).get('delivery_hints')}`",
        f"- installed_required_skills: `{','.join(sorted((payload.get('skills') or {}).keys()))}`",
        f"- user_local_bin_on_path: `{(payload.get('path') or {}).get('user_local_bin_on_path')}`",
        f"- python: `{(payload.get('python') or {}).get('executable')}`",
        "",
        "## Checks",
    ]
    for check in payload.get("checks") or []:
        required = "required" if check.get("required") else "optional"
        lines.append(f"- {check.get('id')} ({required}): `{check.get('ok')}` - {check.get('detail')}")
    provenance = payload.get("release_provenance") if isinstance(payload.get("release_provenance"), dict) else {}
    if provenance:
        default_release = provenance.get("default_release") if isinstance(provenance.get("default_release"), dict) else {}
        live_canary = provenance.get("live_canary") if isinstance(provenance.get("live_canary"), dict) else {}
        current = provenance.get("current_invocation") if isinstance(provenance.get("current_invocation"), dict) else {}
        readiness = (
            provenance.get("promotion_readiness")
            if isinstance(provenance.get("promotion_readiness"), dict)
            else {}
        )
        lines.extend(
            [
                "",
                "## Release Provenance",
                (
                    "- default_release: "
                    f"root=`{default_release.get('root')}`, "
                    f"release_id=`{default_release.get('release_id')}`, "
                    f"is_release_snapshot=`{default_release.get('is_release_snapshot')}`"
                ),
                (
                    "- live_canary: "
                    f"root=`{live_canary.get('root')}`, "
                    f"separate_from_default=`{live_canary.get('separate_from_default')}`"
                ),
                (
                    "- current_invocation: "
                    f"source=`{current.get('source')}`, "
                    f"repo_root=`{current.get('repo_root')}`"
                ),
                (
                    "- latest_promotion_readiness: "
                    f"available=`{readiness.get('available')}`, "
                    f"goal=`{readiness.get('goal_id')}`, "
                    f"generated_at=`{readiness.get('generated_at')}`, "
                    f"classification=`{readiness.get('classification')}`, "
                    f"outcome=`{readiness.get('delivery_outcome')}`, "
                    f"freshness=`{readiness.get('freshness_status')}`, "
                    f"age_hours=`{readiness.get('age_hours')}`, "
                    f"requires_readiness_run=`{readiness.get('requires_readiness_run')}`"
                ),
            ]
        )
    if not payload.get("ok"):
        lines.extend(["", "## Fix", str(payload.get("fix"))])
    return "\n".join(lines)
