"""Compatibility imports for the OpenViking extension's project scope."""

from ...extensions.openviking_semantic_preference.project_peer import (
    PROJECT_PEER_PREFIX,
    ProjectPeerScope,
    project_peer_id,
    resolve_project_identity,
    resolve_project_peer_scope,
)
from ...repository_identity import normalize_repository_identity

__all__ = [
    "PROJECT_PEER_PREFIX",
    "ProjectPeerScope",
    "normalize_repository_identity",
    "project_peer_id",
    "resolve_project_identity",
    "resolve_project_peer_scope",
]
