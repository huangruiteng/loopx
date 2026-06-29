from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from . import __version__


RELEASE_MANIFEST_SCHEMA_VERSION = "loopx_release_manifest_v0"
RELEASE_MANIFEST_FILENAME = "release.json"


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


def build_release_manifest(
    *,
    release_root: Path,
    release_id: str,
    installed_at: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    source_env = env or os.environ
    archive_url = source_env.get("LOOPX_ARCHIVE_URL")
    archive_sha256 = source_env.get("LOOPX_ARCHIVE_SHA256")
    repo = source_env.get("LOOPX_REPO")
    ref = source_env.get("LOOPX_REF")
    source_kind = "github_archive" if archive_url else "local_checkout"
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
        "package": {
            "name": "loopx",
            "version": __version__,
        },
        "source": {
            "kind": source_kind,
            "repo": repo,
            "ref": ref,
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
    installed_at: str | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    manifest = build_release_manifest(
        release_root=release_root,
        release_id=release_id,
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
    parser.add_argument("--installed-at")
    args = parser.parse_args(argv)
    write_release_manifest(
        release_root=Path(args.release_root),
        release_id=args.release_id,
        installed_at=args.installed_at,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
