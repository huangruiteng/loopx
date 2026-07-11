"""Reusable bounded context-provider integrations for LoopX capabilities."""

from .base import (
    canonical_context_text,
    canonical_context_lines,
    canonical_context_matches,
    ContextProviderItem,
    ContextProviderRetrieval,
    ContextProviderSync,
)
from .openviking import OpenVikingContextProvider
from .factory import build_context_provider
from .repository_lifecycle import (
    RepositoryContextActivation,
    RepositoryContextRevisionPlan,
    activate_repository_context_revision,
)

__all__ = [
    "ContextProviderItem",
    "ContextProviderRetrieval",
    "ContextProviderSync",
    "OpenVikingContextProvider",
    "RepositoryContextActivation",
    "RepositoryContextRevisionPlan",
    "activate_repository_context_revision",
    "build_context_provider",
    "canonical_context_text",
    "canonical_context_lines",
    "canonical_context_matches",
]
