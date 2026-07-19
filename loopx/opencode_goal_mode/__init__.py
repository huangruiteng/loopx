from __future__ import annotations

from importlib import resources


def plugin_source() -> str:
    return resources.files(__package__).joinpath("loopx-goal.js").read_text(encoding="utf-8")


def runtime_source() -> str:
    return resources.files(__package__).joinpath("goal-bridge-runtime.mjs").read_text(
        encoding="utf-8"
    )
