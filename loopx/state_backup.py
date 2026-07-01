from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
from typing import Any

from . import __version__
from .paths import DEFAULT_RUNTIME_ROOT


STATE_BACKUP_SCHEMA_VERSION = "loopx_state_backup_v0"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _should_skip(path: Path, exclude_roots: list[Path]) -> bool:
    resolved = _resolved(path)
    return any(resolved == root or _is_relative_to(resolved, root) for root in exclude_roots)


def _path_stats(path: Path, exclude_roots: list[Path]) -> tuple[dict[str, int], list[str]]:
    stats = {"paths": 0, "files": 0, "directories": 0, "symlinks": 0, "bytes": 0}
    warnings: list[str] = []

    def visit(item: Path) -> None:
        if _should_skip(item, exclude_roots):
            return
        try:
            stat = item.lstat()
        except OSError as exc:
            warnings.append(f"could not stat {item}: {exc}")
            return
        stats["paths"] += 1
        stats["bytes"] += int(stat.st_size)
        if item.is_symlink():
            stats["symlinks"] += 1
            return
        if item.is_dir():
            stats["directories"] += 1
            try:
                children = sorted(item.iterdir(), key=lambda child: child.name)
            except OSError as exc:
                warnings.append(f"could not list {item}: {exc}")
                return
            for child in children:
                visit(child)
            return
        stats["files"] += 1

    visit(path)
    return stats, warnings


def _target(
    *,
    key: str,
    source_path: Path,
    archive_path: str,
    exclude_roots: list[Path],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    if not source_path.exists() and not source_path.is_symlink():
        return None, {"key": key, "source_path": str(source_path), "reason": "path does not exist"}, []
    stats, warnings = _path_stats(source_path, exclude_roots)
    return (
        {
            "key": key,
            "source_path": str(source_path),
            "archive_path": archive_path,
            "stats": stats,
        },
        None,
        warnings,
    )


def _discover_targets(
    *,
    project: Path,
    runtime_root: Path,
    output_dir: Path,
    include_automations: bool,
    include_skills: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    targets: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    warnings: list[str] = []
    exclude_roots = [_resolved(output_dir)]

    def add(key: str, source_path: Path, archive_path: str) -> None:
        found, absent, target_warnings = _target(
            key=key,
            source_path=source_path.expanduser(),
            archive_path=archive_path,
            exclude_roots=exclude_roots,
        )
        if found is not None:
            targets.append(found)
        if absent is not None:
            missing.append(absent)
        warnings.extend(target_warnings)

    add("runtime_root", runtime_root, "runtime-root")
    add("project_loopx", project / ".loopx", "project/.loopx")
    add("project_codex_goals", project / ".codex" / "goals", "project/.codex/goals")
    add("project_local_goals", project / ".local" / "goals", "project/.local/goals")

    codex_home = _codex_home()
    if include_automations:
        add("codex_automations", codex_home / "automations", "codex/automations")
    if include_skills:
        skills_root = codex_home / "skills"
        skill_dirs = sorted(skills_root.glob("loopx-*")) if skills_root.exists() else []
        if skill_dirs:
            for skill_dir in skill_dirs:
                add(f"codex_skill:{skill_dir.name}", skill_dir, f"codex/skills/{skill_dir.name}")
        else:
            missing.append(
                {
                    "key": "codex_loopx_skills",
                    "source_path": str(skills_root / "loopx-*"),
                    "reason": "no loopx-* skills found",
                }
            )
    return targets, missing, warnings


def build_state_backup_plan(
    *,
    project: Path | str = ".",
    runtime_root: Path | str | None = None,
    output_dir: Path | str | None = None,
    backup_id: str | None = None,
    include_automations: bool = True,
    include_skills: bool = True,
) -> dict[str, Any]:
    resolved_project = _resolved(Path(project))
    resolved_runtime_root = _resolved(Path(runtime_root).expanduser() if runtime_root else DEFAULT_RUNTIME_ROOT)
    resolved_output_dir = _resolved(Path(output_dir).expanduser() if output_dir else resolved_runtime_root / "backups")
    resolved_backup_id = backup_id or _utc_timestamp()
    archive_path = resolved_output_dir / f"loopx-state-{resolved_backup_id}.tar.gz"
    manifest_path = resolved_output_dir / f"loopx-state-{resolved_backup_id}.manifest.json"
    targets, missing, warnings = _discover_targets(
        project=resolved_project,
        runtime_root=resolved_runtime_root,
        output_dir=resolved_output_dir,
        include_automations=include_automations,
        include_skills=include_skills,
    )
    total_stats = {
        "paths": sum(int(item.get("stats", {}).get("paths", 0)) for item in targets),
        "files": sum(int(item.get("stats", {}).get("files", 0)) for item in targets),
        "directories": sum(int(item.get("stats", {}).get("directories", 0)) for item in targets),
        "symlinks": sum(int(item.get("stats", {}).get("symlinks", 0)) for item in targets),
        "bytes": sum(int(item.get("stats", {}).get("bytes", 0)) for item in targets),
    }
    return {
        "ok": True,
        "schema_version": STATE_BACKUP_SCHEMA_VERSION,
        "mode": "state_backup",
        "dry_run": True,
        "execute_requested": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backup_id": resolved_backup_id,
        "project": str(resolved_project),
        "runtime_root": str(resolved_runtime_root),
        "codex_home": str(_codex_home()),
        "output_dir": str(resolved_output_dir),
        "archive_path": str(archive_path),
        "manifest_path": str(manifest_path),
        "included": targets,
        "missing": missing,
        "warnings": warnings,
        "summary": {
            "included_target_count": len(targets),
            "missing_target_count": len(missing),
            "warning_count": len(warnings),
            "total_stats": total_stats,
        },
        "execution": None,
        "recommended_action": (
            "run `loopx backup-state --execute` to write the private local backup"
            if targets
            else "no backup targets found; check --project, --runtime-root, and CODEX_HOME"
        ),
    }


def _add_path_to_tar(tar: tarfile.TarFile, source: Path, archive_path: str, exclude_roots: list[Path]) -> None:
    if _should_skip(source, exclude_roots):
        return
    if source.is_dir() and not source.is_symlink():
        tar.add(source, arcname=archive_path, recursive=False)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            _add_path_to_tar(tar, child, f"{archive_path}/{child.name}", exclude_roots)
        return
    tar.add(source, arcname=archive_path, recursive=False)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def execute_state_backup_plan(payload: dict[str, Any]) -> dict[str, Any]:
    archive_path = Path(str(payload["archive_path"])).expanduser()
    manifest_path = Path(str(payload["manifest_path"])).expanduser()
    output_dir = Path(str(payload["output_dir"])).expanduser()
    included = payload.get("included") if isinstance(payload.get("included"), list) else []
    if not included:
        updated = dict(payload)
        updated["ok"] = False
        updated["execute_requested"] = True
        updated["recommended_action"] = "no backup targets found; nothing was written"
        return updated

    output_dir.mkdir(parents=True, exist_ok=True)
    exclude_roots = [_resolved(output_dir)]
    updated = dict(payload)
    updated["dry_run"] = False
    updated["execute_requested"] = True
    updated["package_version"] = __version__
    updated["execution"] = {
        "archive_path": str(archive_path),
        "manifest_path": str(manifest_path),
        "archive_sha256": None,
        "archive_size_bytes": None,
    }
    updated["recommended_action"] = "backup written; keep the archive local and private"

    manifest_for_archive = dict(updated)
    manifest_bytes = json.dumps(manifest_for_archive, ensure_ascii=False, indent=2).encode("utf-8")
    with tarfile.open(archive_path, "w:gz", dereference=False) as tar:
        for item in included:
            if not isinstance(item, dict):
                continue
            source = Path(str(item.get("source_path") or "")).expanduser()
            archive_name = str(item.get("archive_path") or source.name)
            if source.exists() or source.is_symlink():
                _add_path_to_tar(tar, source, archive_name, exclude_roots)
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest_bytes)
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        tar.addfile(info, io.BytesIO(manifest_bytes))

    execution = dict(updated["execution"])
    execution["archive_sha256"] = _sha256_file(archive_path)
    execution["archive_size_bytes"] = archive_path.stat().st_size
    updated["execution"] = execution
    manifest_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return updated


def render_state_backup_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    total = summary.get("total_stats") if isinstance(summary.get("total_stats"), dict) else {}
    lines = [
        "# LoopX State Backup",
        "",
        f"- OK: `{payload.get('ok')}`",
        f"- Dry run: `{payload.get('dry_run')}`",
        f"- Backup id: `{payload.get('backup_id')}`",
        f"- Project: `{payload.get('project')}`",
        f"- Runtime root: `{payload.get('runtime_root')}`",
        f"- Output dir: `{payload.get('output_dir')}`",
        f"- Included targets: `{summary.get('included_target_count')}`",
        f"- Missing targets: `{summary.get('missing_target_count')}`",
        f"- Total paths: `{total.get('paths')}`",
        f"- Total bytes: `{total.get('bytes')}`",
        f"- Recommended action: {payload.get('recommended_action')}",
    ]
    execution = payload.get("execution")
    if isinstance(execution, dict):
        lines.extend(
            [
                "",
                "## Written Files",
                "",
                f"- Archive: `{execution.get('archive_path')}`",
                f"- Manifest: `{execution.get('manifest_path')}`",
                f"- Archive sha256: `{execution.get('archive_sha256')}`",
                f"- Archive bytes: `{execution.get('archive_size_bytes')}`",
            ]
        )
    included = payload.get("included") if isinstance(payload.get("included"), list) else []
    if included:
        lines.extend(["", "## Included", ""])
        for item in included:
            if isinstance(item, dict):
                stats = item.get("stats") if isinstance(item.get("stats"), dict) else {}
                lines.append(
                    f"- `{item.get('key')}` -> `{item.get('archive_path')}` "
                    f"({stats.get('paths')} paths)"
                )
    missing = payload.get("missing") if isinstance(payload.get("missing"), list) else []
    if missing:
        lines.extend(["", "## Missing", ""])
        for item in missing:
            if isinstance(item, dict):
                lines.append(f"- `{item.get('key')}`: {item.get('reason')}")
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"
