from __future__ import annotations

import os
from pathlib import Path

ZCODE_INSTALL_SURFACE = "zcode"
ZCODE_HOME_ENV = "ZCODE_AGENTS_HOME"
DEFAULT_ZCODE_HOME = ".agents"
SKILLS_SUBDIR = "skills"
SKILLS_ROOT_LABEL = "AGENTS_HOME/skills"


def zcode_home(value: str | None = None) -> Path:
    """ZCode discovers user skills from AGENTS_HOME/skills (default ~/.agents).

    ZCode has no goal primitive and no host automation scheduler; like the other
    skill-facade CLI hosts it is driven by the agent's own turn loop gated by
    LoopX quota. Project-local skills under ``<repo>/.agents/skills`` shadow the
    user root, so installs target the user root and stay project independent.
    """
    raw = value or os.environ.get(ZCODE_HOME_ENV) or str(Path.home() / DEFAULT_ZCODE_HOME)
    return Path(raw).expanduser()
