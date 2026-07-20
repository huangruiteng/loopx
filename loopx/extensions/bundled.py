from __future__ import annotations

from importlib import resources
from pathlib import Path


BUNDLED_EXTENSION_PACKAGES = {
    "loopx-lark": "loopx.extensions.lark",
    "openviking-periodic-report": (
        "loopx.extensions.openviking_periodic_report"
    ),
    "openviking-semantic-preference": (
        "loopx.extensions.openviking_semantic_preference"
    ),
}
BUNDLED_EXTENSION_IDS = tuple(BUNDLED_EXTENSION_PACKAGES)


def bundled_extension_manifest(extension_id: str) -> Path:
    wanted = str(extension_id or "").strip()
    package = BUNDLED_EXTENSION_PACKAGES.get(wanted)
    if package is None:
        raise ValueError(
            f"unknown bundled extension `{wanted}`; expected one of "
            f"{list(BUNDLED_EXTENSION_IDS)}"
        )
    manifest = resources.files(package).joinpath("extension.toml")
    return Path(str(manifest))
