"""Compatibility gate for the optional Core presentation API."""
from __future__ import annotations

from importlib import import_module
from types import ModuleType


_PRESENTATION_MODULE = "loopx.extensions.presentation"
_PRESENTATION_ATTRIBUTES = (
    "load_presentation_view_validator",
)


def presentation_api_error() -> str | None:
    """Return a public-safe explanation when Core lacks the dashboard API."""

    try:
        module: ModuleType = import_module(_PRESENTATION_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name in {_PRESENTATION_MODULE, "loopx.extensions"}:
            return (
                "the installed loopx version does not provide the extension "
                "presentation API required for finance research dashboards"
            )
        raise
    missing = [name for name in _PRESENTATION_ATTRIBUTES if not hasattr(module, name)]
    if missing:
        return (
            "the installed loopx version has an incomplete extension presentation "
            f"API (missing {', '.join(missing)})"
        )
    return None


def require_presentation_api() -> None:
    """Fail with an actionable error before loading the dashboard runtime."""

    if error := presentation_api_error():
        raise RuntimeError(f"Finance dashboard compatibility check failed: {error}.")
