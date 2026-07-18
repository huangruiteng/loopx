from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from ...repository_identity import resolve_project_identity


PROJECT_PEER_PREFIX = "project-"
_SAFE_USER_SPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


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
