from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from . import __version__


RELEASE_MANIFEST_SCHEMA_VERSION = "loopx_release_manifest_v0"
RELEASE_MANIFEST_FILENAME = "release.json"
PACKAGE_VERSION_SOURCE = "loopx.__version__"


def release_version_tag(version: str | None = None) -> str | None:
    selected = __version__ if version is None else version
    if not isinstance(selected, str):
        return None
    text = selected.strip()
    if not text:
        return None
    return text if text.startswith("v") else f"v{text}"


def package_release_metadata() -> dict[str, str | None]:
    return {
        "name": "loopx",
        "version": __version__,
        "version_tag": release_version_tag(__version__),
        "version_source": PACKAGE_VERSION_SOURCE,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_tree(root: Path) -> dict[str, Any]:
    if not root.exists():
        return {
            "available": False,
            "sha256": None,
            "file_count": 0,
            "reason": "path does not exist",
        }

    digest = hashlib.sha256()
    file_count = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        file_hash = _sha256_file(path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
        file_count += 1
    return {
        "available": True,
        "sha256": digest.hexdigest(),
        "file_count": file_count,
    }


def _run_git(source_root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _git_metadata(source_root: Path | None) -> dict[str, Any]:
    if source_root is None:
        return {
            "git_commit": None,
            "git_ref": None,
            "git_dirty": None,
        }
    root = source_root.expanduser().resolve()
    if not root.exists():
        return {
            "git_commit": None,
            "git_ref": None,
            "git_dirty": None,
        }
    commit = _run_git(root, ["rev-parse", "HEAD"])
    branch = _run_git(root, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    tag = _run_git(root, ["describe", "--tags", "--exact-match"])
    status = _run_git(root, ["status", "--porcelain"])
    if commit is None and branch is None and tag is None and status is None:
        dirty: bool | None = None
    else:
        dirty = bool(status)
    return {
        "git_commit": commit,
        "git_ref": branch or tag,
        "git_dirty": dirty,
    }


def _manifest_source_metadata(source_root: Path | None) -> dict[str, Any]:
    if source_root is None:
        return {
            "git_commit": None,
            "git_ref": None,
            "git_dirty": None,
            "kind": None,
            "repo": None,
            "ref": None,
            "archive_url": None,
            "archive_sha256": None,
            "promotion_mode": None,
        }
    manifest_path = source_root.expanduser() / RELEASE_MANIFEST_FILENAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "git_commit": None,
            "git_ref": None,
            "git_dirty": None,
            "kind": None,
            "repo": None,
            "ref": None,
            "archive_url": None,
            "archive_sha256": None,
            "promotion_mode": None,
        }
    source = manifest.get("source") if isinstance(manifest, dict) else None
    if not isinstance(source, dict):
        return {
            "git_commit": None,
            "git_ref": None,
            "git_dirty": None,
            "kind": None,
            "repo": None,
            "ref": None,
            "archive_url": None,
            "archive_sha256": None,
            "promotion_mode": None,
        }
    return {
        "git_commit": source.get("git_commit"),
        "git_ref": source.get("git_ref") or source.get("ref"),
        "git_dirty": source.get("git_dirty"),
        "kind": source.get("kind"),
        "repo": source.get("repo"),
        "ref": source.get("ref"),
        "archive_url": source.get("archive_url"),
        "archive_sha256": source.get("archive_sha256"),
        "promotion_mode": source.get("promotion_mode"),
    }


def _source_metadata(source_root: Path | None) -> dict[str, Any]:
    git_metadata = _git_metadata(source_root)
    if any(git_metadata.get(key) is not None for key in ("git_commit", "git_ref", "git_dirty")):
        return {
            **git_metadata,
            "kind": None,
            "repo": None,
            "ref": None,
            "archive_url": None,
            "archive_sha256": None,
            "promotion_mode": None,
        }
    return _manifest_source_metadata(source_root)


def build_release_manifest(
    *,
    release_root: Path,
    release_id: str,
    source_root: Path | None = None,
    installed_at: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_env = env or os.environ
    source_metadata = _source_metadata(source_root)
    archive_url = source_env.get("LOOPX_ARCHIVE_URL") or source_metadata.get("archive_url")
    archive_sha256 = source_env.get("LOOPX_ARCHIVE_SHA256") or source_metadata.get("archive_sha256")
    repo = source_env.get("LOOPX_REPO") or source_metadata.get("repo")
    ref = source_env.get("LOOPX_REF") or source_metadata.get("ref")
    source_kind = "github_archive" if archive_url else (source_metadata.get("kind") or "local_checkout")
    promotion_mode = source_env.get("LOOPX_PROMOTION_MODE") or source_metadata.get("promotion_mode")
    skills_root = release_root / "skills"
    skills: dict[str, Any] = {}
    if skills_root.exists():
        for skill_dir in sorted(item for item in skills_root.iterdir() if item.is_dir()):
            skills[skill_dir.name] = _hash_tree(skill_dir)
    skills_digest = hashlib.sha256(
        json.dumps(skills, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "release_id": release_id,
        "installed_at": installed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "package": package_release_metadata(),
        "source": {
            "kind": source_kind,
            "promotion_mode": promotion_mode,
            "repo": repo,
            "ref": ref,
            "git_commit": source_metadata["git_commit"],
            "git_ref": source_metadata["git_ref"],
            "git_dirty": source_metadata["git_dirty"],
            "archive_url": archive_url,
            "archive_sha256": archive_sha256,
        },
        "skills": {
            "digest": skills_digest,
            "items": skills,
        },
    }


def write_release_manifest(
    *,
    release_root: Path,
    release_id: str,
    source_root: Path | None = None,
    installed_at: str | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    manifest = build_release_manifest(
        release_root=release_root,
        release_id=release_id,
        source_root=source_root,
        installed_at=installed_at,
        env=env,
    )
    manifest_path = release_root / RELEASE_MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def load_release_manifest(release_root: Path | None) -> dict[str, Any]:
    if release_root is None:
        return {
            "available": False,
            "path": None,
            "reason": "release root is not available",
            "manifest": None,
        }
    manifest_path = release_root / RELEASE_MANIFEST_FILENAME
    if not manifest_path.exists():
        return {
            "available": False,
            "path": str(manifest_path),
            "reason": "release manifest does not exist",
            "manifest": None,
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "path": str(manifest_path),
            "reason": f"release manifest is unreadable: {exc}",
            "manifest": None,
        }
    if not isinstance(manifest, dict):
        return {
            "available": False,
            "path": str(manifest_path),
            "reason": "release manifest is not an object",
            "manifest": None,
        }
    return {
        "available": True,
        "path": str(manifest_path),
        "reason": None,
        "manifest": manifest,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Write a LoopX release manifest.")
    parser.add_argument("release_root")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--source-root")
    parser.add_argument("--installed-at")
    args = parser.parse_args(argv)
    write_release_manifest(
        release_root=Path(args.release_root),
        release_id=args.release_id,
        source_root=Path(args.source_root) if args.source_root else None,
        installed_at=args.installed_at,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
