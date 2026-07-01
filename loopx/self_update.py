from __future__ import annotations

from pathlib import Path
import os
import shlex
import subprocess
from typing import Any

from .doctor import NO_CLONE_INSTALL_URL, collect_doctor


UPDATE_PLAN_SCHEMA_VERSION = "loopx_update_plan_v0"
DEFAULT_UPDATE_REPO = "huangruiteng/loopx"
DEFAULT_UPDATE_REF = "stable"
ROLLBACK_PREVIOUS_ALIAS = "previous"


def _source_config(
    *,
    repo: str | None,
    ref: str | None,
    archive_url: str | None,
) -> dict[str, Any]:
    selected_repo = repo or os.environ.get("LOOPX_REPO") or DEFAULT_UPDATE_REPO
    ref_override = ref or os.environ.get("LOOPX_REF")
    selected_ref = ref_override or DEFAULT_UPDATE_REF
    archive_url_override = archive_url or os.environ.get("LOOPX_ARCHIVE_URL")
    selected_archive_url = archive_url_override
    if not selected_archive_url:
        selected_archive_url = f"https://codeload.github.com/{selected_repo}/tar.gz/{selected_ref}"
    if archive_url_override:
        channel = "github_archive_url_override"
    elif ref_override:
        channel = "github_archive_override"
    else:
        channel = "github_archive_stable"
    return {
        "channel": channel,
        "repo": selected_repo,
        "ref": selected_ref,
        "ref_source": "default_stable" if not ref_override else "override",
        "archive_url": selected_archive_url,
        "installer_url": NO_CLONE_INSTALL_URL,
    }


def _command_for_source(source: dict[str, Any]) -> str:
    exports = [
        f"LOOPX_REPO={shlex.quote(str(source['repo']))}",
        f"LOOPX_REF={shlex.quote(str(source['ref']))}",
    ]
    archive_url = source.get("archive_url")
    if archive_url:
        exports.append(f"LOOPX_ARCHIVE_URL={shlex.quote(str(archive_url))}")
    return (
        " ".join(exports)
        + f" curl -fsSL {shlex.quote(str(source['installer_url']))} | bash\n"
        'export PATH="$HOME/.local/bin:$PATH"\n'
        "loopx doctor"
    )


def _release_root_from_doctor(doctor_payload: dict[str, Any]) -> str | None:
    package = doctor_payload.get("package") if isinstance(doctor_payload.get("package"), dict) else {}
    release_root = package.get("release_root")
    if isinstance(release_root, str) and release_root:
        return release_root
    path = doctor_payload.get("path") if isinstance(doctor_payload.get("path"), dict) else {}
    realpath = path.get("loopx_realpath")
    if isinstance(realpath, str) and realpath:
        realpath_path = Path(realpath)
        if realpath_path.name == "loopx" and realpath_path.parent.name == "scripts":
            return str(realpath_path.parent.parent)
    return None


def _user_loopx_bin(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".local" / "bin" / "loopx"


def _user_releases_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".local" / "share" / "loopx" / "releases"


def _release_script(release_root: Path) -> Path:
    return release_root / "scripts" / "loopx"


def _list_release_roots(releases_dir: Path) -> list[Path]:
    if not releases_dir.exists():
        return []
    return sorted(
        (
            item
            for item in releases_dir.iterdir()
            if item.is_dir() and _release_script(item).exists()
        ),
        key=lambda item: item.name,
        reverse=True,
    )


def _rollback_release_command(release_id: str) -> str:
    return f"loopx update --rollback {shlex.quote(release_id)}\nloopx doctor"


def _rollback_plan(doctor_payload: dict[str, Any]) -> dict[str, Any]:
    release_root = _release_root_from_doctor(doctor_payload)
    if not release_root:
        return {
            "available": False,
            "reason": "current loopx command is not a release snapshot",
            "current_release_root": None,
            "rollback_command": None,
        }
    release_id = Path(release_root).name
    return {
        "available": True,
        "reason": "current release snapshot can be restored with the first-class rollback CLI",
        "rollback_release_id": release_id,
        "current_release_root": release_root,
        "rollback_command": _rollback_release_command(release_id),
    }


def build_rollback_plan(
    *,
    release_id: str,
    doctor_payload: dict[str, Any] | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    doctor = doctor_payload or collect_doctor()
    current_release_root = _release_root_from_doctor(doctor)
    releases_dir = _user_releases_dir(home)
    releases = _list_release_roots(releases_dir)
    current_root_path = Path(current_release_root).resolve() if current_release_root else None
    requested_release_id = release_id.strip()
    selected: Path | None = None
    reason = None

    if not requested_release_id:
        reason = "rollback release id is required"
    elif requested_release_id == ROLLBACK_PREVIOUS_ALIAS:
        for candidate in releases:
            if current_root_path and candidate.resolve() == current_root_path:
                continue
            selected = candidate
            break
        if selected is None:
            reason = "no previous release snapshot found"
    elif "/" in requested_release_id or requested_release_id in {".", ".."}:
        reason = "rollback release id must be a release directory name"
    else:
        candidate = releases_dir / requested_release_id
        if not _release_script(candidate).exists():
            reason = f"release snapshot not found: {requested_release_id}"
        else:
            selected = candidate

    available = selected is not None
    selected_release_id = selected.name if selected else None
    selected_release_root = str(selected) if selected else None
    return {
        "ok": available,
        "schema_version": UPDATE_PLAN_SCHEMA_VERSION,
        "mode": "rollback",
        "dry_run": False,
        "execute_requested": True,
        "requested_release_id": requested_release_id,
        "current": {
            "current_release_root": current_release_root,
        },
        "plan": {
            "action": "rollback",
            "available": available,
            "reason": reason,
            "releases_dir": str(releases_dir),
            "release_count": len(releases),
            "selected_release_id": selected_release_id,
            "selected_release_root": selected_release_root,
            "rollback_command": _rollback_release_command(requested_release_id),
            "mutates_loopx_runtime_state": False,
            "mutates_release_install": True,
            "post_rollback_validation": "loopx doctor",
        },
        "execution": None,
        "recommended_action": (
            "rollback target selected; execute rollback and validate with doctor"
            if available
            else "choose an existing release id or use `loopx update --rollback previous` when available"
        ),
    }


def build_update_plan(
    *,
    repo: str | None = None,
    ref: str | None = None,
    archive_url: str | None = None,
    check_only: bool = False,
    execute: bool = False,
    doctor_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doctor = doctor_payload or collect_doctor()
    install_freshness = (
        doctor.get("install_freshness")
        if isinstance(doctor.get("install_freshness"), dict)
        else {}
    )
    release_manifest = (
        doctor.get("release_manifest")
        if isinstance(doctor.get("release_manifest"), dict)
        else {}
    )
    release_manifest_body = (
        release_manifest.get("manifest")
        if isinstance(release_manifest.get("manifest"), dict)
        else {}
    )
    source = _source_config(repo=repo, ref=ref, archive_url=archive_url)
    install_command = _command_for_source(source)
    dry_run = not execute
    path = doctor.get("path") if isinstance(doctor.get("path"), dict) else {}
    requires_upgrade = install_freshness.get("requires_upgrade")
    if execute:
        recommended_action = "review execution result and post-update doctor output"
    elif requires_upgrade is False:
        recommended_action = (
            "no update needed; use `loopx update --dry-run` or "
            "`loopx update --execute` only to force a refresh"
        )
    elif check_only:
        recommended_action = "run `loopx update --dry-run` to review the source and rollback plan"
    else:
        recommended_action = "run `loopx update --execute` if you accept the source and rollback plan"
    return {
        "ok": True,
        "schema_version": UPDATE_PLAN_SCHEMA_VERSION,
        "mode": "update",
        "check_only": check_only,
        "dry_run": dry_run,
        "execute_requested": execute,
        "source": source,
        "current": {
            "loopx_command": path.get("loopx"),
            "loopx_realpath": path.get("loopx_realpath"),
            "current_version": install_freshness.get("current_version"),
            "release_id": install_freshness.get("release_id"),
            "install_freshness_status": install_freshness.get("status"),
            "requires_upgrade": requires_upgrade,
            "reason": install_freshness.get("reason"),
            "release_manifest_available": release_manifest.get("available"),
            "release_manifest_path": release_manifest.get("path"),
            "release_manifest": release_manifest_body,
        },
        "plan": {
            "action": "check_only" if check_only else "execute_installer" if execute else "dry_run",
            "install_command": install_command,
            "post_update_validation": "loopx doctor",
            "mutates_loopx_runtime_state": False,
            "mutates_release_install": execute,
            "backup": _rollback_plan(doctor),
        },
        "execution": None,
        "recommended_action": recommended_action,
    }


def execute_update_plan(payload: dict[str, Any], *, timeout_seconds: int = 600) -> dict[str, Any]:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    installer_url = str(source.get("installer_url") or NO_CLONE_INSTALL_URL)
    env = os.environ.copy()
    env["LOOPX_REPO"] = str(source.get("repo") or DEFAULT_UPDATE_REPO)
    env["LOOPX_REF"] = str(source.get("ref") or DEFAULT_UPDATE_REF)
    if source.get("archive_url"):
        env["LOOPX_ARCHIVE_URL"] = str(source["archive_url"])
    install_result = subprocess.run(
        ["bash", "-lc", f"curl -fsSL {shlex.quote(installer_url)} | bash"],
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout_seconds,
    )
    loopx_bin = Path.home() / ".local" / "bin" / "loopx"
    doctor_result = subprocess.run(
        [str(loopx_bin), "--format", "json", "doctor"],
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout_seconds,
    )
    execution = {
        "install_returncode": install_result.returncode,
        "doctor_returncode": doctor_result.returncode,
        "install_stdout_tail": install_result.stdout[-2000:],
        "install_stderr_tail": install_result.stderr[-2000:],
        "doctor_stdout_tail": doctor_result.stdout[-2000:],
        "doctor_stderr_tail": doctor_result.stderr[-2000:],
    }
    updated = dict(payload)
    updated["execution"] = execution
    updated["ok"] = install_result.returncode == 0 and doctor_result.returncode == 0
    if not updated["ok"]:
        updated["recommended_action"] = "inspect update execution tails and restore from rollback plan if needed"
    return updated


def execute_rollback_plan(
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 600,
    home: Path | None = None,
) -> dict[str, Any]:
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    selected_release_root = plan.get("selected_release_root")
    if not payload.get("ok") or not selected_release_root:
        return payload
    release_root = Path(str(selected_release_root))
    target_script = _release_script(release_root)
    loopx_bin = _user_loopx_bin(home)
    previous_link_target = os.readlink(loopx_bin) if loopx_bin.is_symlink() else None
    execution: dict[str, Any] = {
        "target_script": str(target_script),
        "loopx_command": str(loopx_bin),
        "previous_link_target": previous_link_target,
        "restored_previous_on_failure": False,
    }
    updated = dict(payload)
    try:
        loopx_bin.parent.mkdir(parents=True, exist_ok=True)
        temp_link = loopx_bin.with_name(f".{loopx_bin.name}.rollback.{os.getpid()}")
        if temp_link.exists() or temp_link.is_symlink():
            temp_link.unlink()
        temp_link.symlink_to(target_script)
        os.replace(temp_link, loopx_bin)
        doctor_result = subprocess.run(
            [str(loopx_bin), "--format", "json", "doctor"],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        execution.update(
            {
                "doctor_returncode": doctor_result.returncode,
                "doctor_stdout_tail": doctor_result.stdout[-2000:],
                "doctor_stderr_tail": doctor_result.stderr[-2000:],
            }
        )
        updated["ok"] = doctor_result.returncode == 0
        if not updated["ok"] and previous_link_target:
            restore_link = loopx_bin.with_name(f".{loopx_bin.name}.rollback.restore.{os.getpid()}")
            if restore_link.exists() or restore_link.is_symlink():
                restore_link.unlink()
            restore_link.symlink_to(previous_link_target)
            os.replace(restore_link, loopx_bin)
            execution["restored_previous_on_failure"] = True
    except Exception as exc:
        execution["error"] = str(exc)
        updated["ok"] = False
        if previous_link_target:
            restore_link = loopx_bin.with_name(f".{loopx_bin.name}.rollback.restore.{os.getpid()}")
            try:
                if restore_link.exists() or restore_link.is_symlink():
                    restore_link.unlink()
                restore_link.symlink_to(previous_link_target)
                os.replace(restore_link, loopx_bin)
                execution["restored_previous_on_failure"] = True
            except Exception as restore_exc:
                execution["restore_error"] = str(restore_exc)
    finally:
        if "temp_link" in locals() and (temp_link.exists() or temp_link.is_symlink()):
            temp_link.unlink()
        if "restore_link" in locals() and (restore_link.exists() or restore_link.is_symlink()):
            restore_link.unlink()
    updated["execution"] = execution
    updated["recommended_action"] = (
        "rollback complete; review doctor output"
        if updated["ok"]
        else "rollback failed; inspect execution error before retrying"
    )
    return updated


def render_update_plan_markdown(payload: dict[str, Any]) -> str:
    if payload.get("mode") == "rollback":
        plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else None
        lines = [
            "# LoopX Update Rollback",
            "",
            f"- OK: `{payload.get('ok')}`",
            f"- Requested release: `{payload.get('requested_release_id')}`",
            f"- Selected release: `{plan.get('selected_release_id')}`",
            f"- Selected root: `{plan.get('selected_release_root')}`",
            f"- Reason: `{plan.get('reason')}`",
            f"- Runtime state mutation: `{plan.get('mutates_loopx_runtime_state')}`",
            f"- Release install mutation: `{plan.get('mutates_release_install')}`",
            f"- Recommended action: {payload.get('recommended_action')}",
        ]
        rollback_command = plan.get("rollback_command")
        if rollback_command:
            lines.extend(["", "## Rollback Command", "", "```bash", str(rollback_command), "```"])
        if execution:
            lines.extend(
                [
                    "",
                    "## Execution",
                    "",
                    f"- Doctor return code: `{execution.get('doctor_returncode')}`",
                ]
            )
        return "\n".join(lines) + "\n"

    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    backup = plan.get("backup") if isinstance(plan.get("backup"), dict) else {}
    lines = [
        "# LoopX Update",
        "",
        f"- OK: `{payload.get('ok')}`",
        f"- Mode: `{plan.get('action')}`",
        f"- Dry run: `{payload.get('dry_run')}`",
        f"- Source: `{source.get('repo')}` @ `{source.get('ref')}`",
        f"- Current version: `{current.get('current_version')}`",
        f"- Freshness: `{current.get('install_freshness_status')}`",
        f"- Requires upgrade: `{current.get('requires_upgrade')}`",
        f"- Runtime state mutation: `{plan.get('mutates_loopx_runtime_state')}`",
        f"- Release install mutation: `{plan.get('mutates_release_install')}`",
        f"- Rollback available: `{backup.get('available')}`",
        f"- Recommended action: {payload.get('recommended_action')}",
        "",
        "## Install Command",
        "",
        "```bash",
        str(plan.get("install_command") or ""),
        "```",
    ]
    rollback_command = backup.get("rollback_command")
    if rollback_command:
        lines.extend(["", "## Rollback Command", "", "```bash", str(rollback_command), "```"])
    execution = payload.get("execution")
    if isinstance(execution, dict):
        lines.extend(
            [
                "",
                "## Execution",
                "",
                f"- Install return code: `{execution.get('install_returncode')}`",
                f"- Doctor return code: `{execution.get('doctor_returncode')}`",
            ]
        )
    return "\n".join(lines) + "\n"
