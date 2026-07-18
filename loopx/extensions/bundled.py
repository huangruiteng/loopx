from __future__ import annotations

from importlib import resources
from pathlib import Path


BUNDLED_EXTENSION_IDS = ("openviking-semantic-preference",)


def bundled_extension_manifest(extension_id: str) -> Path:
    wanted = str(extension_id or "").strip()
    if wanted != "openviking-semantic-preference":
        raise ValueError(
            f"unknown bundled extension `{wanted}`; expected one of "
            f"{list(BUNDLED_EXTENSION_IDS)}"
        )
    manifest = resources.files(
        "loopx.extensions.openviking_semantic_preference"
    ).joinpath("extension.toml")
    return Path(str(manifest))
