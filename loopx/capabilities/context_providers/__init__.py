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
from .service_ownership import (
    context_provider_service_restarted,
    load_context_provider_service_ownership,
)

__all__ = [
    "ContextProviderItem",
    "ContextProviderRetrieval",
    "ContextProviderSync",
    "OpenVikingContextProvider",
    "build_context_provider",
    "context_provider_service_restarted",
    "load_context_provider_service_ownership",
    "canonical_context_text",
    "canonical_context_lines",
    "canonical_context_matches",
]
