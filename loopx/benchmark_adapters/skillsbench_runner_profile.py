from __future__ import annotations

import argparse
import json
import os
import shlex
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION = "skillsbench_runner_profile_v0"
SKILLSBENCH_RUNNER_PROFILE_RELATIVE_PATH = Path(
    "loopx/skillsbench/runner-profile.json"
)
REQUIRED_RUNNER_ENV = (
    "SKILLSBENCH_SSH_DESTINATION",
    "SKILLSBENCH_REMOTE_ROOT",
    "SKILLSBENCH_ROOT",
    "SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD",
)
ALLOWED_RUNNER_ENV = frozenset(
    {
        *REQUIRED_RUNNER_ENV,
        "SKILLSBENCH_REMOTE_CODEX_BIN",
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_COMMAND",
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_SOLVER_COMMAND",
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND",
        "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND_INSTRUMENTED",
        "SKILLSBENCH_LOOPX_TURN_VALIDATION_COMMAND",
        "SKILLSBENCH_SSH_OPTIONS",
    }
)


class SkillsBenchRunnerProfileError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def default_skillsbench_runner_profile_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    source = environment if environment is not None else os.environ
    state_home = str(source.get("XDG_STATE_HOME") or "")
    if state_home:
        root = Path(state_home).expanduser()
    else:
        home = str(source.get("HOME") or "")
        if not home:
            raise SkillsBenchRunnerProfileError("profile_default_path_unavailable")
        root = Path(home).expanduser() / ".local" / "state"
    if not root.is_absolute():
        raise SkillsBenchRunnerProfileError("profile_default_path_invalid")
    return root / SKILLSBENCH_RUNNER_PROFILE_RELATIVE_PATH


def _profile_file(path: Path) -> Path:
    try:
        file_stat = path.lstat()
    except OSError as error:
        raise SkillsBenchRunnerProfileError("profile_unreadable") from error
    if not stat.S_ISREG(file_stat.st_mode):
        raise SkillsBenchRunnerProfileError("profile_not_regular_file")
    if file_stat.st_uid != os.getuid():
        raise SkillsBenchRunnerProfileError("profile_not_owned_by_current_user")
    if stat.S_IMODE(file_stat.st_mode) & 0o077:
        raise SkillsBenchRunnerProfileError("profile_permissions_not_owner_only")
    return path


def load_skillsbench_runner_profile(path: Path) -> dict[str, str]:
    profile_path = _profile_file(path)
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SkillsBenchRunnerProfileError("profile_json_invalid") from error
    if not isinstance(payload, Mapping):
        raise SkillsBenchRunnerProfileError("profile_root_invalid")
    if payload.get("schema_version") != SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION:
        raise SkillsBenchRunnerProfileError("profile_schema_unsupported")
    if set(payload) - {"schema_version", "environment"}:
        raise SkillsBenchRunnerProfileError("profile_root_key_unknown")
    environment = payload.get("environment")
    if not isinstance(environment, Mapping):
        raise SkillsBenchRunnerProfileError("profile_environment_invalid")
    unknown = set(environment) - ALLOWED_RUNNER_ENV
    if unknown:
        raise SkillsBenchRunnerProfileError("profile_environment_key_unknown")

    normalized: dict[str, str] = {}
    for key, value in environment.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value:
            raise SkillsBenchRunnerProfileError("profile_environment_value_invalid")
        if "\x00" in value:
            raise SkillsBenchRunnerProfileError("profile_environment_value_invalid")
        normalized[key] = value
    return normalized


def skillsbench_runner_profile_shell_exports(
    profile: Mapping[str, str],
    *,
    current_environment: Mapping[str, str] | None = None,
) -> str:
    environment = current_environment if current_environment is not None else os.environ
    lines = []
    for key in sorted(profile):
        if environment.get(key):
            continue
        lines.append(f"export {key}={shlex.quote(profile[key])}")
    return "\n".join(lines)


def capture_skillsbench_runner_profile(
    path: Path,
    *,
    environment: Mapping[str, str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    source = environment if environment is not None else os.environ
    captured = {
        key: str(source[key])
        for key in sorted(ALLOWED_RUNNER_ENV)
        if str(source.get(key) or "")
    }
    missing = [key for key in REQUIRED_RUNNER_ENV if key not in captured]
    if missing:
        raise SkillsBenchRunnerProfileError("required_runner_environment_missing")
    if path.exists() and not force:
        raise SkillsBenchRunnerProfileError("profile_already_exists")

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = {
        "schema_version": SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION,
        "environment": captured,
    }
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
        path.chmod(0o600)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise SkillsBenchRunnerProfileError("profile_write_failed") from error
    return skillsbench_runner_profile_summary(captured)


def skillsbench_runner_profile_summary(
    profile: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION,
        "environment_key_count": len(profile),
        "required_environment_complete": all(
            profile.get(key) for key in REQUIRED_RUNNER_ENV
        ),
        "profile_path_recorded": False,
        "profile_values_recorded": False,
        "owner_only_permissions_required": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Capture or load an owner-only local SkillsBench runner profile "
            "without printing private values in public summaries."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("export-shell", "inspect"):
        command = commands.add_parser(name)
        command.add_argument("--profile", type=Path)
        if name == "export-shell":
            command.add_argument("--if-present", action="store_true")
    capture = commands.add_parser("capture")
    capture.add_argument("--profile", type=Path)
    capture.add_argument("--force", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        profile_path = args.profile or default_skillsbench_runner_profile_path()
        if args.command == "capture":
            summary = capture_skillsbench_runner_profile(
                profile_path,
                force=args.force,
            )
            print(json.dumps(summary, sort_keys=True))
            return 0
        if (
            args.command == "export-shell"
            and args.if_present
            and not profile_path.exists()
            and not profile_path.is_symlink()
        ):
            return 0
        profile = load_skillsbench_runner_profile(profile_path)
        if args.command == "inspect":
            print(json.dumps(skillsbench_runner_profile_summary(profile), sort_keys=True))
            return 0
        exports = skillsbench_runner_profile_shell_exports(profile)
        if exports:
            print(exports)
        print("export SKILLSBENCH_RUNNER_PROFILE_DISCOVERED=1")
        return 0
    except SkillsBenchRunnerProfileError as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "schema_version": SKILLSBENCH_RUNNER_PROFILE_SCHEMA_VERSION,
                    "error": error.code,
                    "profile_path_recorded": False,
                    "profile_values_recorded": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
