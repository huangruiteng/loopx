from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


CAPABILITY_ORIGINS = frozenset({"builtin", "extension"})
CAPABILITY_VISIBILITIES = frozenset({"public", "internal"})
REQUIRED_CAPABILITY_FIELDS = (
    "id",
    "title",
    "status",
    "user_value",
    "next_real_step",
)
REQUIRED_PUBLIC_CAPABILITY_FIELDS = ("real_world_anchor", "entry_command")


def _required_string(record: Mapping[str, Any], key: str, *, context: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} requires non-empty string `{key}`")
    return value.strip()


class CapabilityRegistry:
    """Compose capability records from built-in and enabled extension providers."""

    def __init__(self) -> None:
        self._providers: dict[str, dict[str, Any]] = {}
        self._records: dict[str, dict[str, Any]] = {}
        self._implementations: dict[str, list[dict[str, Any]]] = {}

    def register_provider(self, provider: Mapping[str, Any]) -> None:
        provider_id = _required_string(provider, "id", context="provider")
        origin = _required_string(
            provider, "origin", context=f"provider `{provider_id}`"
        )
        if origin not in CAPABILITY_ORIGINS:
            raise ValueError(
                f"provider `{provider_id}` has unsupported origin `{origin}`; "
                f"expected one of {sorted(CAPABILITY_ORIGINS)}"
            )
        if provider_id in self._providers:
            raise ValueError(f"duplicate capability provider `{provider_id}`")
        normalized = deepcopy(dict(provider))
        normalized["id"] = provider_id
        normalized["origin"] = origin
        normalized["enabled"] = bool(provider.get("enabled", True))
        self._providers[provider_id] = normalized

    def register_capability(self, record: Mapping[str, Any]) -> None:
        capability_id = _required_string(record, "id", context="capability")
        context = f"capability `{capability_id}`"
        for key in REQUIRED_CAPABILITY_FIELDS:
            _required_string(record, key, context=context)

        origin = _required_string(record, "origin", context=context)
        if origin not in CAPABILITY_ORIGINS:
            raise ValueError(
                f"{context} has unsupported origin `{origin}`; "
                f"expected one of {sorted(CAPABILITY_ORIGINS)}"
            )
        visibility = _required_string(record, "visibility", context=context)
        if visibility not in CAPABILITY_VISIBILITIES:
            raise ValueError(
                f"{context} has unsupported visibility `{visibility}`; "
                f"expected one of {sorted(CAPABILITY_VISIBILITIES)}"
            )
        if visibility == "public":
            for key in REQUIRED_PUBLIC_CAPABILITY_FIELDS:
                _required_string(record, key, context=context)
        provider_id = _required_string(record, "provider_id", context=context)
        provider = self._providers.get(provider_id)
        if provider is None:
            raise ValueError(f"{context} references unknown provider `{provider_id}`")
        if provider["origin"] != origin:
            raise ValueError(
                f"{context} origin `{origin}` does not match provider "
                f"`{provider_id}` origin `{provider['origin']}`"
            )
        if capability_id in self._records:
            previous = self._records[capability_id]
            raise ValueError(
                f"duplicate capability `{capability_id}` from providers "
                f"`{previous['provider_id']}` and `{provider_id}`"
            )

        normalized = deepcopy(dict(record))
        normalized["id"] = capability_id
        normalized["origin"] = origin
        normalized["visibility"] = visibility
        normalized["provider_id"] = provider_id
        self._records[capability_id] = normalized

    def register_implementation(self, implementation: Mapping[str, Any]) -> None:
        capability_id = _required_string(
            implementation,
            "capability_id",
            context="capability implementation",
        )
        context = f"capability implementation `{capability_id}`"
        provider_id = _required_string(implementation, "provider_id", context=context)
        protocol = _required_string(implementation, "protocol", context=context)
        if capability_id not in self._records:
            raise ValueError(f"{context} references unknown capability")
        if provider_id not in self._providers:
            raise ValueError(f"{context} references unknown provider `{provider_id}`")
        existing = self._implementations.setdefault(capability_id, [])
        if any(item["provider_id"] == provider_id for item in existing):
            raise ValueError(
                f"duplicate implementation for capability `{capability_id}` "
                f"from provider `{provider_id}`"
            )
        normalized = deepcopy(dict(implementation))
        normalized["capability_id"] = capability_id
        normalized["provider_id"] = provider_id
        normalized["protocol"] = protocol
        existing.append(normalized)

    def _with_implementations(self, record: Mapping[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(dict(record))
        implementations = self._implementations.get(str(record["id"]), [])
        if implementations:
            normalized["implementation_providers"] = deepcopy(implementations)
        return normalized

    def capability_ids(self, *, include_internal: bool = False) -> list[str]:
        return [
            capability_id
            for capability_id, record in self._records.items()
            if include_internal or record["visibility"] == "public"
        ]

    def get(
        self,
        capability_id: str,
        *,
        include_internal: bool = False,
    ) -> dict[str, Any]:
        wanted = str(capability_id or "").strip()
        record = self._records.get(wanted)
        if record is None or (
            record["visibility"] == "internal" and not include_internal
        ):
            raise ValueError(
                f"unknown capability `{wanted}`; expected one of "
                f"{self.capability_ids(include_internal=include_internal)}"
            )
        return self._with_implementations(record)

    def records(self, *, include_internal: bool = False) -> list[dict[str, Any]]:
        return [
            self._with_implementations(record)
            for record in self._records.values()
            if include_internal or record["visibility"] == "public"
        ]

    def providers(self) -> list[dict[str, Any]]:
        return [deepcopy(provider) for provider in self._providers.values()]
