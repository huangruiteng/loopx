from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .base import ContextProvider


ContextProviderBuilder = Callable[[Mapping[str, Any]], ContextProvider]
_CONTEXT_PROVIDER_BUILDERS: dict[str, ContextProviderBuilder] = {}


def register_context_provider(
    provider_id: str,
    builder: ContextProviderBuilder,
) -> None:
    normalized = str(provider_id or "").strip()
    if not normalized:
        raise ValueError("context provider id is required")
    if normalized in _CONTEXT_PROVIDER_BUILDERS:
        raise ValueError(f"context provider already registered: {normalized}")
    _CONTEXT_PROVIDER_BUILDERS[normalized] = builder


def build_context_provider(config: Mapping[str, Any]) -> ContextProvider:
    """Resolve one configured provider without capability-specific branching."""

    provider_id = str(config.get("provider") or "").strip()
    builder = _CONTEXT_PROVIDER_BUILDERS.get(provider_id)
    if builder is None:
        raise ValueError(f"unsupported context provider: {provider_id or '<missing>'}")
    return builder(config)
