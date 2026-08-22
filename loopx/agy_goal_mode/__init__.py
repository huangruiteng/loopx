from __future__ import annotations

import os
from pathlib import Path

AGY_INSTALL_SURFACE = "agy"
AGY_HOME_ENV = "AGY_CLI_HOME"
DEFAULT_AGY_HOME = ".gemini/antigravity-cli"
SKILLS_SUBDIR = "skills"
SKILLS_ROOT_LABEL = "AGY_CLI_HOME/skills"


def agy_home(value: str | None = None) -> Path:
    """Antigravity CLI discovers user skills from AGY_CLI_HOME/skills.

    The Antigravity CLI binary is ``agy``. It has no goal primitive and no host
    automation scheduler; like the other skill-facade CLI hosts it is driven by
    the agent's own turn loop gated by LoopX quota. The global skills root is
    ``~/.gemini/antigravity-cli/skills`` (directory-style ``SKILL.md`` entries)
    and is shared with no other host, so installs there cannot collide with the
    ZCode or Gemini CLI surfaces.
    """
    raw = value or os.environ.get(AGY_HOME_ENV) or str(Path.home() / DEFAULT_AGY_HOME)
    return Path(raw).expanduser()
