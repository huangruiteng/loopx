from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_PEER_PREFIX = "project-"
_SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_SAFE_USER_SPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def normalize_repository_identity(remote_url: str) -> str:
    """Return a credential-free identity shared by common Git transports."""

    raw = str(remote_url or "").strip()
    if not raw:
        raise ValueError("repository remote URL is required")

    scp_match = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", raw)
    if scp_match and "://" not in raw:
        raw = f"ssh://{scp_match.group(1)}/{scp_match.group(2)}"

    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"git", "http", "https", "ssh"}
        or not parsed.hostname
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("repository remote must be a supported repository URL")

    host = parsed.hostname.casefold()
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("repository remote has an invalid port") from exc
    if port and not (
        (parsed.scheme in {"http", "git"} and port == 80)
        or (parsed.scheme in {"https", "ssh"} and port in {22, 443})
    ):
        host = f"{host}:{port}"

    path = re.sub(r"/+", "/", parsed.path).strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not path:
        raise ValueError("repository remote must include a repository path")
    return f"git:{host}/{path}"


def _origin_remote(project: Path, git_bin: str) -> str:
    try:
        completed = subprocess.run(
            [git_bin, "-C", str(project), "config", "--get", "remote.origin.url"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("project origin remote could not be read") from exc
    if completed.returncode != 0 or not completed.stdout.strip():
        raise ValueError(
            "project has no canonical origin remote; provide a stable LoopX project id"
        )
    return completed.stdout.strip()


def resolve_project_identity(
    project: str | Path,
    *,
    loopx_project_id: str | None = None,
    remote_url: str | None = None,
    git_bin: str = "git",
) -> str:
    """Resolve a durable project identity without using a checkout path."""

    try:
        remote = remote_url or _origin_remote(Path(project), git_bin)
        return normalize_repository_identity(remote)
    except ValueError:
        project_id = str(loopx_project_id or "").strip()
        if not _SAFE_PROJECT_ID.fullmatch(project_id):
            raise
        return f"loopx:{project_id}"


def project_peer_id(project_identity: str) -> str:
    digest = hashlib.sha256(project_identity.encode("utf-8")).hexdigest()[:16]
    return f"{PROJECT_PEER_PREFIX}{digest}"


@dataclass(frozen=True)
class ProjectPeerScope:
    project_identity: str
    peer_id: str
    user_space: str

    @property
    def memory_uri(self) -> str:
        return f"viking://user/{self.user_space}/peers/{self.peer_id}/memories"

    @property
    def preferences_uri(self) -> str:
        return f"{self.memory_uri}/preferences"

    @property
    def global_memory_uri(self) -> str:
        return f"viking://user/{self.user_space}/memories"

    def recall_targets(
        self, *, include_global_fallback: bool = False
    ) -> tuple[str, ...]:
        targets = [self.memory_uri]
        if include_global_fallback:
            targets.append(self.global_memory_uri)
        return tuple(targets)


def resolve_project_peer_scope(
    project: str | Path,
    *,
    user_space: str = "default",
    loopx_project_id: str | None = None,
    remote_url: str | None = None,
    git_bin: str = "git",
) -> ProjectPeerScope:
    normalized_user = str(user_space or "").strip()
    if not _SAFE_USER_SPACE.fullmatch(normalized_user):
        raise ValueError("user space must be a path-safe identifier")
    identity = resolve_project_identity(
        project,
        loopx_project_id=loopx_project_id,
        remote_url=remote_url,
        git_bin=git_bin,
    )
    return ProjectPeerScope(
        project_identity=identity,
        peer_id=project_peer_id(identity),
        user_space=normalized_user,
    )
