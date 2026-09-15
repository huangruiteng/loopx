"""Harbor Codex adapter that stages native binaries without container egress.

LHTB contains offline task containers, so installing Codex from npm inside a
trial would violate the task network policy. This adapter copies the native
Codex bundle from ``CODEX_OFFLINE_DIR`` and otherwise retains Harbor's Codex
configuration and trajectory handling.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harbor.agents.installed.base import CliFlag
from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment


_DEFAULT_OFFLINE_DIR = str(Path(__file__).resolve().parent.parent / "codex")
_STAGE_DIR = os.path.join(tempfile.gettempdir(), "codex-offline")

# These settings tolerate transient gateway failures. Persistent throttling
# should be addressed by reducing ``n_concurrent_trials``.
_RETRY_FLAGS = (
    "-c model_providers.harbor.name=harbor"
    " -c model_providers.harbor.request_max_retries=8"
    " -c model_providers.harbor.stream_max_retries=8"
    " -c model_providers.harbor.stream_idle_timeout_ms=300000"
)


class CodexOffline(Codex):
    """Codex with explicit Goal/Web Search flags and offline installation."""

    CLI_FLAGS = Codex.CLI_FLAGS + [
        CliFlag(
            "goals",
            cli="-c",
            type="enum",
            choices=["true", "false"],
            format="-c features.goals={value}",
        ),
        CliFlag(
            "web_search",
            cli="-c",
            type="enum",
            choices=["disabled", "cached", "live"],
            format='-c web_search="{value}"',
        ),
    ]

    @staticmethod
    def name() -> str:
        return "codex-offline"

    def version(self) -> str | None:
        return self._version or "offline"

    def get_version_command(self) -> str | None:
        return "/usr/local/bin/codex --version"

    def build_cli_flags(self) -> str:
        flags = super().build_cli_flags()
        # Disable server-side Web Search independently of shell networking.
        if "web_search=" not in flags:
            flags = f'{flags} -c web_search="disabled"'.strip()
        return f"{flags} {_RETRY_FLAGS}" if flags else _RETRY_FLAGS

    async def install(self, environment: BaseEnvironment) -> None:
        offline_dir = Path(os.environ.get("CODEX_OFFLINE_DIR", _DEFAULT_OFFLINE_DIR))
        # Resolve symlinks because Harbor upload does not follow them.
        codex_bin = (offline_dir / "codex").resolve()
        rg_bin = (offline_dir / "rg").resolve()
        sidecar_bin = (offline_dir / "codex-code-mode-host").resolve()
        bwrap_bin = offline_dir / "codex-resources" / "bwrap"

        if not codex_bin.is_file():
            raise FileNotFoundError(
                f"Codex binary not found: {codex_bin}. "
                "Point CODEX_OFFLINE_DIR at the native Codex bundle."
            )
        if not sidecar_bin.is_file():
            raise FileNotFoundError(
                f"codex-code-mode-host not found: {sidecar_bin}. "
                "Point CODEX_OFFLINE_DIR at the complete native Codex bundle."
            )

        await self.exec_as_root(environment, command=f"mkdir -p {_STAGE_DIR}")
        await environment.upload_file(codex_bin, f"{_STAGE_DIR}/codex")
        await environment.upload_file(
            sidecar_bin, f"{_STAGE_DIR}/codex-code-mode-host"
        )
        if rg_bin.is_file():
            await environment.upload_file(rg_bin, f"{_STAGE_DIR}/rg")
        if bwrap_bin.is_file():
            await environment.upload_file(bwrap_bin, f"{_STAGE_DIR}/bwrap")

        # Install with explicit modes and retain a version/fingerprint receipt.
        await self.exec_as_root(
            environment,
            command=(
                "set -eu; "
                f"install -m 0755 {_STAGE_DIR}/codex /usr/local/bin/codex; "
                f"install -m 0755 {_STAGE_DIR}/codex-code-mode-host "
                "  /usr/local/bin/codex-code-mode-host; "
                f"if [ -f {_STAGE_DIR}/rg ]; then "
                f"  install -m 0755 {_STAGE_DIR}/rg /usr/local/bin/rg; "
                "fi; "
                f"if [ -f {_STAGE_DIR}/bwrap ]; then "
                f"  install -m 0755 {_STAGE_DIR}/bwrap /usr/local/bin/bwrap; "
                "fi; "
                f"rm -rf {_STAGE_DIR}; "
                "mkdir -p /logs/agent; "
                "{ /usr/local/bin/codex --version; "
                "  md5sum /usr/local/bin/codex /usr/local/bin/codex-code-mode-host; "
                "} > /logs/agent/codex_version.txt 2>&1; "
                "cat /logs/agent/codex_version.txt"
            ),
        )

        self.logger.info("staged Codex bundle from %s", offline_dir)
