#!/usr/bin/env python3
"""Add an opt-in model-only network mode to Harbor's Docker provider.

Codex runs inside the task container and needs a route to its model gateway.
For an LHTB task with ``allow_internet=false``, Harbor normally applies
``network_mode: none``, which blocks both public egress and model access. This
patch replaces that mode, only when ``LHTB_MODELONLY_NET`` is set, with an
internal Docker network that can reach a gateway bound to the bridge address
but has no public route.

Without the environment flag, Harbor's behavior is unchanged. The patch is
idempotent and can be rerun after checking out a compatible Harbor revision.
"""

import os
import shutil
import sys
import time
from pathlib import Path

HARBOR = Path(os.environ.get("LHTB_HARBOR_SRC", str(Path(__file__).resolve().parents[2] / "upstream" / "harbor" / "src" / "harbor")))
DOCKER_DIR = HARBOR / "environments" / "docker"
INIT_PY = DOCKER_DIR / "__init__.py"
DOCKER_PY = DOCKER_DIR / "docker.py"

MARK = "LHTB_MODELONLY_NET"

INIT_OLD = 'COMPOSE_NO_NETWORK_PATH = COMPOSE_DIR / "docker-compose-no-network.yaml"'
INIT_NEW = INIT_OLD + """
# Optional overlays that separate model access from public internet access.
COMPOSE_MODELONLY_PATH = COMPOSE_DIR / "docker-compose-modelonly.yaml"
COMPOSE_MODELONLY_PLUS_PATH = COMPOSE_DIR / "docker-compose-modelonly-plus.yaml\""""

IMPORT_OLD = """from harbor.environments.docker import (
    COMPOSE_BASE_PATH,
    COMPOSE_BUILD_PATH,
    COMPOSE_NO_NETWORK_PATH,
    COMPOSE_PREBUILT_PATH,
    COMPOSE_WINDOWS_KEEPALIVE_PATH,
    write_mounts_compose_file,
)"""
IMPORT_NEW = """from harbor.environments.docker import (
    COMPOSE_BASE_PATH,
    COMPOSE_BUILD_PATH,
    COMPOSE_MODELONLY_PATH,
    COMPOSE_MODELONLY_PLUS_PATH,
    COMPOSE_NO_NETWORK_PATH,
    COMPOSE_PREBUILT_PATH,
    COMPOSE_WINDOWS_KEEPALIVE_PATH,
    write_mounts_compose_file,
)"""

ATTR_OLD = "    _DOCKER_COMPOSE_NO_NETWORK_PATH = COMPOSE_NO_NETWORK_PATH"
ATTR_NEW = (
    ATTR_OLD
    + """
    _DOCKER_COMPOSE_MODELONLY_PATH = COMPOSE_MODELONLY_PATH
    _DOCKER_COMPOSE_MODELONLY_PLUS_PATH = COMPOSE_MODELONLY_PLUS_PATH"""
)

BRANCH_OLD = """        if not self.task_env_config.allow_internet:
            paths.append(self._DOCKER_COMPOSE_NO_NETWORK_PATH)

        return paths"""
BRANCH_NEW = """        modelonly = bool(os.environ.get("LHTB_MODELONLY_NET"))

        # Network selection is task-scoped. Separate verifier mode is handled
        # by Harbor's trial layer and must not replace the task's network.
        if not self.task_env_config.allow_internet:
            # The default remains network_mode:none. Opt-in offline tasks use
            # the internal bridge and retain the no-public-egress constraint.
            paths.append(
                self._DOCKER_COMPOSE_MODELONLY_PATH
                if modelonly
                else self._DOCKER_COMPOSE_NO_NETWORK_PATH
            )
        elif modelonly:
            # Online tasks keep their default network and gain the model-only
            # interface so every task can use one gateway URL.
            paths.append(self._DOCKER_COMPOSE_MODELONLY_PLUS_PATH)

        return paths"""


def patch(path: Path, pairs: list[tuple[str, str]]) -> bool:
    text = path.read_text()
    if MARK in text or all(new in text for _, new in pairs):
        print(f"  {path.name}: already patched")
        return False
    for old, new in pairs:
        if old not in text:
            sys.exit(f"FATAL: compatible anchor not found in {path}\n---\n{old}\n---")
        if text.count(old) != 1:
            sys.exit(f"FATAL: anchor occurs {text.count(old)} times in {path}")
        text = text.replace(old, new)
    backup = path.with_suffix(path.suffix + f".bak-modelonly-{time.strftime('%H%M%S')}")
    shutil.copy2(path, backup)
    path.write_text(text)
    print(f"  {path.name}: patched (backup: {backup.name})")
    return True


def main() -> None:
    staging = Path(__file__).parent
    for name in ("docker-compose-modelonly.yaml", "docker-compose-modelonly-plus.yaml"):
        src = staging / name
        if not src.exists():
            sys.exit(f"FATAL: missing {src}")
        shutil.copy2(src, DOCKER_DIR / name)
        print(f"  installed {name}")

    patch(INIT_PY, [(INIT_OLD, INIT_NEW)])
    patch(DOCKER_PY, [(IMPORT_OLD, IMPORT_NEW), (ATTR_OLD, ATTR_NEW), (BRANCH_OLD, BRANCH_NEW)])

    # Import smoke: the new compose constants must be available.
    sys.path.insert(0, str(HARBOR.parent))
    import os as _os

    _os.environ.pop("LHTB_MODELONLY_NET", None)
    from harbor.environments.docker import (  # noqa: F401
        COMPOSE_MODELONLY_PATH,
        COMPOSE_MODELONLY_PLUS_PATH,
    )

    assert COMPOSE_MODELONLY_PATH.exists(), COMPOSE_MODELONLY_PATH
    assert COMPOSE_MODELONLY_PLUS_PATH.exists(), COMPOSE_MODELONLY_PLUS_PATH
    print("  import smoke passed")


if __name__ == "__main__":
    main()
