from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import ContextProvider
from .openviking import OpenVikingContextProvider


def build_context_provider(config: Mapping[str, Any]) -> ContextProvider:
    """Resolve one configured provider without capability-specific branching."""

    provider_id = str(config.get("provider") or "").strip()
    if provider_id == "openviking":
        return OpenVikingContextProvider(
            executable=str(config.get("provider_binary") or "ov"),
            minimum_version=str(config.get("minimum_provider_version") or "0.4.9"),
            actor_peer_id=str(config.get("actor_peer_id") or "").strip() or None,
        )
    raise ValueError(f"unsupported context provider: {provider_id or '<missing>'}")
