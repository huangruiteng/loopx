#!/usr/bin/env python3
"""Smoke-test the local checkout default/canary promotion boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-local.sh"


def run_install(env: dict[str, str], *, release_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(INSTALL_SCRIPT)],
        cwd=REPO_ROOT,
        env={**env, "LOOPX_RELEASE_ID": release_id},
        check=True,
        capture_output=True,
        text=True,
    )


def base_env(root: Path) -> tuple[dict[str, str], Path, Path]:
    home = root / "home"
    bin_dir = home / ".local" / "bin"
    releases_dir = home / ".local" / "share" / "loopx" / "releases"
    bin_dir.mkdir(parents=True)
    env = {
        **os.environ,
        "HOME": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "LOOPX_BIN_DIR": str(bin_dir),
        "LOOPX_RELEASES_DIR": str(releases_dir),
        "LOOPX_SHELL_PROFILE": str(home / ".zshrc"),
        "LOOPX_INSTALL_CANARY": "1",
        "LOOPX_INSTALL_SKILL": "0",
        "LOOPX_INSTALL_SLASH_COMMANDS": "0",
        "LOOPX_INSTALL_CLAUDE": "0",
        "LOOPX_APPROVED_DEFAULT_REF": "HEAD^",
        "LOOPX_PYTHON": sys.executable,
        "PATH": os.environ.get("PATH", ""),
        "SHELL": "/bin/zsh",
    }
    return env, bin_dir, releases_dir


def assert_untrusted_checkout_is_canary_only() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-promotion-canary-only-") as tmp:
        env, bin_dir, releases_dir = base_env(Path(tmp))
        default = bin_dir / "loopx"
        default.write_text("#!/usr/bin/env bash\nexit 41\n", encoding="utf-8")
        default.chmod(0o755)

        install = run_install(env, release_id="guarded-untrusted")
        assert install.returncode == 0, install.stderr
        assert "loopx checkout installed as canary only" in install.stdout, install.stdout
        assert "promotion mode: canary_only_untrusted_checkout" in install.stdout, install.stdout
        assert not default.is_symlink(), default
        assert "exit 41" in default.read_text(encoding="utf-8"), default
        canary = bin_dir / "loopx-canary"
        assert canary.is_symlink(), canary
        assert canary.resolve() == REPO_ROOT / "scripts" / "loopx", canary.resolve()
        assert not releases_dir.exists(), releases_dir


def assert_explicit_promotion_is_auditable() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-promotion-explicit-") as tmp:
        env, bin_dir, _releases_dir = base_env(Path(tmp))
        env["LOOPX_PROMOTE_DEFAULT"] = "1"

        install = run_install(env, release_id="explicit-promotion")
        assert install.returncode == 0, install.stderr
        assert "loopx installed locally" in install.stdout, install.stdout
        assert "promotion mode: explicit_override" in install.stdout, install.stdout
        default = bin_dir / "loopx"
        assert default.is_symlink(), default
        release_root = default.resolve().parents[1]
        manifest = json.loads((release_root / "release.json").read_text(encoding="utf-8"))
        assert manifest["source"]["promotion_mode"] == "explicit_override", manifest

        doctor = subprocess.run(
            [str(default), "--format", "json", "doctor"],
            env={**env, "PATH": f"{bin_dir}:{env['PATH']}"},
            check=True,
            capture_output=True,
            text=True,
        )
        doctor_payload = json.loads(doctor.stdout)
        default_release = doctor_payload["release_provenance"]["default_release"]
        assert default_release["promotion_mode"] == "explicit_override", default_release


def main() -> int:
    assert_untrusted_checkout_is_canary_only()
    assert_explicit_promotion_is_auditable()
    print("local-install-promotion-boundary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
