#!/usr/bin/env python3
"""Smoke-test LaunchAgent status output without touching real launchctl."""

from __future__ import annotations

import os
import plistlib
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHAGENT_SCRIPT = REPO_ROOT / "scripts" / "macos-dashboard-launchagent.sh"


def write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def run_script(fake_bin: Path, home: Path, args: list[str], *, schema_version: int, write_enabled: bool = False, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "FAKE_STATUS_CONTRACT_SCHEMA_VERSION": str(schema_version),
        "FAKE_CONTROL_PLANE_WRITE_ENABLED": "true" if write_enabled else "false",
        "LOOPX_STATUS_CONTRACT_MIN_VERSION": "2",
        "CODEX_HOME": "",
        "LOOPX_CHAT_CODEX_HOME": "",
        **(extra_env or {}),
    }
    return subprocess.run(
        [str(LAUNCHAGENT_SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def run_status(fake_bin: Path, home: Path, *, schema_version: int, write_enabled: bool = False) -> str:
    return run_script(fake_bin, home, ["status"], schema_version=schema_version, write_enabled=write_enabled).stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-launchagent-status-smoke-") as raw_tmp:
        tmp = Path(raw_tmp)
        fake_bin = tmp / "bin"
        home = tmp / "home"
        fake_bin.mkdir()
        home.mkdir()

        write_executable(
            fake_bin / "uname",
            "#!/usr/bin/env bash\nprintf 'Darwin\\n'\n",
        )
        write_executable(
            fake_bin / "launchctl",
            "#!/usr/bin/env bash\n"
            "if [[ \"$1\" == \"print\" ]]; then\n"
            "  exit 0\n"
            "fi\n"
            "if [[ \"$1\" == \"bootout\" || \"$1\" == \"bootstrap\" || \"$1\" == \"kickstart\" ]]; then\n"
            "  exit 0\n"
            "fi\n"
            "echo \"unexpected launchctl args: $*\" >&2\n"
            "exit 2\n",
        )
        write_executable(
            fake_bin / "loopx",
            "#!/usr/bin/env bash\n"
            "if [[ \"$*\" == *\"--format json doctor\"* ]]; then\n"
            "  printf '%s\\n' '{\"release_manifest\":{\"manifest\":{\"release_id\":\"current-release\",\"package\":{\"version\":\"0.5.3\"},\"source\":{\"git_commit\":\"current-revision\"}}}}'\n"
            "  exit 0\n"
            "fi\n"
            "echo loopx \"$@\"\n",
        )
        write_executable(
            fake_bin / "loopx-canary",
            "#!/usr/bin/env bash\n"
            "echo loopx-canary \"$@\"\n",
        )
        write_executable(
            fake_bin / "curl",
            "#!/usr/bin/env bash\n"
            "if [[ \"$*\" == *\"/api/chat/capabilities\"* ]]; then\n"
            "  printf '%s\\n' '{\"ok\":true,\"schema_version\":\"loopx_chat_capabilities_v1\",\"runtime_identity\":{\"schema_version\":\"loopx_runtime_identity_v1\",\"package_version\":\"0.5.3\",\"release_id\":\"current-release\",\"source_revision\":\"current-revision\"}}'\n"
            "  exit 0\n"
            "fi\n"
            "version=\"${FAKE_STATUS_CONTRACT_SCHEMA_VERSION:-0}\"\n"
            "write_enabled=\"${FAKE_CONTROL_PLANE_WRITE_ENABLED:-false}\"\n"
            "cat <<EOF\n"
            "{\"ok\":true,\"status_contract\":{\"schema_version\":${version},\"producer\":\"loopx status\"},\"local_dashboard_api\":{\"control_plane_write_enabled\":${write_enabled}}}\n"
            "EOF\n",
        )

        old_output = run_status(fake_bin, home, schema_version=1)
        assert "- com.loopx.status: loaded" in old_output, old_output
        assert "- com.loopx.chat: loaded" in old_output, old_output
        assert "- com.loopx.dashboard" not in old_output, old_output
        assert "- status_contract: schema_version=1 producer=loopx status expected>=2" in old_output, old_output
        assert "- control_plane_write_api: disabled" in old_output, old_output
        assert "warning: status feed is using an old contract; run:" in old_output, old_output
        assert "macos-dashboard-launchagent.sh restart" in old_output, old_output

        current_output = run_status(fake_bin, home, schema_version=2, write_enabled=True)
        assert "- status_contract: schema_version=2 producer=loopx status expected>=2" in current_output, current_output
        assert "- control_plane_write_api: enabled" in current_output, current_output
        assert "warning: control-plane registry writes are enabled" in current_output, current_output
        assert "warning: status feed is using an old contract" not in current_output, current_output
        assert "LaunchAgents:" in current_output, current_output
        assert "URLs:" in current_output, current_output
        assert "Logs:" in current_output, current_output

        run_script(fake_bin, home, ["install"], schema_version=2)
        status_plist = home / "Library" / "LaunchAgents" / "com.loopx.status.plist"
        chat_plist = home / "Library" / "LaunchAgents" / "com.loopx.chat.plist"
        default_plist = status_plist.read_text(encoding="utf-8")
        default_chat_plist = chat_plist.read_text(encoding="utf-8")
        assert "--enable-control-plane-write-api" not in default_plist, default_plist
        assert " chat --global-registry " in default_chat_plist, default_chat_plist
        assert "--port 8767" in default_chat_plist, default_chat_plist
        assert "--replace-existing-loopx-chat" in default_chat_plist, default_chat_plist
        assert "--no-open" in default_chat_plist, default_chat_plist
        assert f"export CODEX_HOME={(home / '.codex').resolve()};" in default_chat_plist, default_chat_plist
        assert "export LOOPX_PYTHON=" in default_plist, default_plist
        assert "export LOOPX_PYTHON=" in default_chat_plist, default_chat_plist
        assert "/loopx --registry" in default_plist, default_plist
        assert "/loopx-canary" not in default_plist, default_plist
        assert not (home / "Library" / "LaunchAgents" / "com.loopx.dashboard.plist").exists(), "retired dashboard LaunchAgent should not be installed"

        run_script(
            fake_bin,
            home,
            ["--enable-control-plane-write-api", "restart"],
            schema_version=2,
            extra_env={"LOOPX_CHAT_CODEX_HOME": str(home / "selected-codex-home")},
        )
        write_plist = status_plist.read_text(encoding="utf-8")
        selected_chat_plist = chat_plist.read_text(encoding="utf-8")
        assert "--enable-control-plane-write-api" in write_plist, write_plist
        selected = (home / 'selected-codex-home').resolve()
        assert f"export CODEX_HOME={selected};" in selected_chat_plist, selected_chat_plist
        run_script(fake_bin, home, ["install"], schema_version=2,
                   extra_env={"CODEX_HOME": str(home / "unrelated-upgrader")})
        assert plistlib.loads(chat_plist.read_bytes())["EnvironmentVariables"]["LOOPX_CHAT_CODEX_HOME"] == str(selected)

        # Legacy generated plists used only a shell export. Preserve quoted
        # paths across upgrades without ever executing their command contents.
        legacy = plistlib.loads(chat_plist.read_bytes())
        legacy.pop("EnvironmentVariables")
        legacy_home = (home / "legacy home").resolve()
        legacy["ProgramArguments"] = ["/bin/zsh", "-c", f"export CODEX_HOME='{legacy_home}'; exec loopx chat"]
        chat_plist.write_bytes(plistlib.dumps(legacy))
        run_script(fake_bin, home, ["install"], schema_version=2,
                   extra_env={"CODEX_HOME": str(home / "unrelated-upgrader")})
        assert plistlib.loads(chat_plist.read_bytes())["EnvironmentVariables"]["LOOPX_CHAT_CODEX_HOME"] == str(legacy_home)

        chat_plist.write_bytes(b"invalid plist")
        try:
            run_script(fake_bin, home, ["install"], schema_version=2)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("malformed existing binding must fail closed")
        assert chat_plist.read_bytes() == b"invalid plist"

    print("macos-dashboard-launchagent-status-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
