#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install-local.sh [--help]

Install LoopX from the current checkout. Installation behavior is configured
through environment variables; positional arguments are not supported.

Options:
  -h, --help  Show this help and exit.

Common environment variables:
  LOOPX_PYTHON=/path/to/python3.11  Use this supported Python for the release.
  LOOPX_PROMOTE_DEFAULT=1          Promote this checkout as the default loopx.
  LOOPX_INSTALL_CANARY=0           Skip the loopx-canary executable.
  LOOPX_INSTALL_SKILL=0            Skip packaged Codex workflow skills.
  LOOPX_INSTALL_SLASH_COMMANDS=0   Skip Codex and Claude command skills.
  LOOPX_INSTALL_OPENCODE=0         Install the OpenCode goal bridge surface.
  CODEX_HOME=/path                 Override the Codex home directory.
EOF
}

case "${1:-}" in
  -h|--help)
    if [[ "$#" -ne 1 ]]; then
      echo "loopx installer error: --help does not accept additional arguments" >&2
      usage >&2
      exit 2
    fi
    usage
    exit 0
    ;;
  "")
    ;;
  *)
    echo "loopx installer error: unknown argument: $1" >&2
    usage >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

bin_dir="${LOOPX_BIN_DIR:-$HOME/.local/bin}"
shell_profile="${LOOPX_SHELL_PROFILE:-}"
codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_dir="${LOOPX_SKILLS_DIR:-$codex_home/skills}"
man_root="${LOOPX_MAN_ROOT:-$HOME/.local/share/man}"
man_dir="${LOOPX_MAN_DIR:-$man_root/man1}"
install_skill="${LOOPX_INSTALL_SKILL:-1}"
install_canary="${LOOPX_INSTALL_CANARY:-1}"
promote_default_request="${LOOPX_PROMOTE_DEFAULT:-auto}"
releases_dir="${LOOPX_RELEASES_DIR:-$HOME/.local/share/loopx/releases}"
release_id_request="${LOOPX_RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
release_id=""
release_dir=""
release_tmp=""
install_lock=""
install_lock_owned=0
legacy_line=""
installed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

configure_python_runtime() {
  local requested="${LOOPX_PYTHON:-python3}"
  local resolved
  if ! command -v "$requested" >/dev/null 2>&1; then
    echo "loopx installer error: Python executable not found: $requested" >&2
    echo "Set LOOPX_PYTHON to a Python 3.11+ executable." >&2
    exit 2
  fi
  if ! resolved="$("$requested" - <<'PY'
import sys

if sys.version_info < (3, 11):
    print(
        "loopx installer error: Python 3.11+ is required; "
        f"selected Python is {sys.version_info.major}.{sys.version_info.minor}",
        file=sys.stderr,
    )
    raise SystemExit(2)
print(sys.executable)
PY
)"; then
    echo "Set LOOPX_PYTHON to a Python 3.11+ executable." >&2
    exit 2
  fi
  export LOOPX_PYTHON="$resolved"
}

cleanup_install_lock() {
  if [[ -n "$release_tmp" && -d "$release_tmp" ]]; then
    rm -rf "$release_tmp"
  fi
  if [[ "$install_lock_owned" == "1" && -n "$install_lock" && -d "$install_lock" ]]; then
    rm -rf "$install_lock"
  fi
}

trap cleanup_install_lock EXIT

run_under_install_guard() {
  if [[ "${LOOPX_INSTALL_GUARD_HELD:-0}" == "1" ]]; then
    return 0
  fi
  local python_bin="${LOOPX_PYTHON:-python3}"
  local guard_file="$releases_dir/.install-guard"
  LOOPX_INSTALL_GUARD_FILE="$guard_file" \
    LOOPX_INSTALL_SCRIPT="$repo_root/scripts/install-local.sh" \
    exec "$python_bin" - "$@" <<'PY'
from pathlib import Path
import fcntl
import os
import sys
import time

guard_path = Path(os.environ["LOOPX_INSTALL_GUARD_FILE"])
script = os.environ["LOOPX_INSTALL_SCRIPT"]
timeout = 60.0

guard_path.parent.mkdir(parents=True, exist_ok=True)
with guard_path.open("a+", encoding="utf-8") as guard:
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                print(
                    "loopx installer error: timed out waiting for another local install to finish",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            time.sleep(0.1)

    os.set_inheritable(guard.fileno(), True)
    env = dict(os.environ)
    env["LOOPX_INSTALL_GUARD_HELD"] = "1"
    os.execve(script, [script, *sys.argv[1:]], env)
PY
}

reserve_release_id() {
  if [[ ! "$release_id_request" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "loopx installer error: LOOPX_RELEASE_ID must be a safe release directory name" >&2
    exit 2
  fi
  local candidate="$release_id_request"
  local suffix=2
  while [[ -e "$releases_dir/$candidate" || -L "$releases_dir/$candidate" ]]; do
    candidate="$release_id_request-$suffix"
    suffix=$((suffix + 1))
  done
  release_id="$candidate"
  release_dir="$releases_dir/$release_id"
  release_tmp="$(mktemp -d "$releases_dir/.${release_id}.tmp.XXXXXX")"
}

acquire_install_lock() {
  install_lock="$releases_dir/.install-lock"
  local attempt=0
  until mkdir "$install_lock" 2>/dev/null; do
    local owner_pid=""
    if [[ -f "$install_lock/pid" ]]; then
      owner_pid="$(cat "$install_lock/pid" 2>/dev/null || true)"
    fi
    if [[ "$owner_pid" =~ ^[0-9]+$ ]] && ! kill -0 "$owner_pid" 2>/dev/null; then
      local stale_lock="$install_lock.stale.$$"
      if mv "$install_lock" "$stale_lock" 2>/dev/null; then
        rm -rf "$stale_lock"
        continue
      fi
    fi
    attempt=$((attempt + 1))
    if [[ "$attempt" -ge 600 ]]; then
      echo "loopx installer error: timed out waiting for another local install to finish" >&2
      exit 1
    fi
    sleep 0.1
  done
  install_lock_owned=1
  printf '%s\n' "$$" >"$install_lock/pid"
}

warn_stale_promotion_readiness() {
  local python_bin="${LOOPX_PYTHON:-python3}"
  local runtime_root="${LOOPX_RUNTIME_ROOT:-$codex_home/loopx}"
  local gate_json
  gate_json="$(PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" -m loopx.cli --runtime-root "$runtime_root" --format json promotion-gate 2>/dev/null || true)"
  if [[ -z "$gate_json" ]]; then
    return 0
  fi
  LOOPX_PROMOTION_GATE_JSON="$gate_json" "$python_bin" - <<'PY' || true
import json
import os
import sys

try:
    payload = json.loads(os.environ.get("LOOPX_PROMOTION_GATE_JSON") or "{}")
except json.JSONDecodeError:
    sys.exit(0)

if not payload.get("should_warn"):
    sys.exit(0)

message = payload.get("warning_message")
if not message:
    message = "promotion-readiness evidence requires a canary readiness run before promotion."
print(f"loopx install warning: {message}", file=sys.stderr)
PY
}

copy_path() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    cp -R "$src" "$dst"
  fi
}

append_legacy_line() {
  local message="$1"
  if [[ -z "$legacy_line" ]]; then
    legacy_line="- $message"
  else
    legacy_line="$legacy_line"$'\n'"- $message"
  fi
}

disable_legacy_shim() {
  local name="$1"
  local legacy="$bin_dir/$name"
  local disabled="$bin_dir/$name.legacy-disabled"
  if [[ ! -e "$legacy" && ! -L "$legacy" ]]; then
    return 0
  fi
  if [[ ! -L "$legacy" ]]; then
    append_legacy_line "legacy command left untouched: $legacy is not a symlink"
    return 0
  fi
  local target
  target="$(readlink "$legacy" || true)"
  if [[ "$target" != *"/goal-harness/"* && "$target" != *".local/share/goal-harness/"* ]]; then
    append_legacy_line "legacy command left untouched: $legacy does not point at a legacy release"
    return 0
  fi
  rm -f "$disabled"
  mv "$legacy" "$disabled"
  append_legacy_line "legacy command disabled: $disabled"
}

install_symlink() {
  local target="$1"
  local link="$2"
  local tmp="$link.tmp.$$"
  rm -f "$tmp"
  if [[ ! -L "$link" && -d "$link" ]]; then
    echo "loopx installer error: $link is a directory; remove it before installing" >&2
    return 1
  fi
  ln -s "$target" "$tmp"
  LOOPX_LINK_TMP="$tmp" LOOPX_LINK_TARGET="$link" "${LOOPX_PYTHON:-python3}" - <<'PY'
import os

os.replace(os.environ["LOOPX_LINK_TMP"], os.environ["LOOPX_LINK_TARGET"])
PY
}

verify_default_promotion() {
  LOOPX_VERIFY_LINK="$bin_dir/loopx" \
    LOOPX_VERIFY_RELEASE_DIR="$release_dir" \
    LOOPX_VERIFY_SOURCE_COMMIT="${LOOPX_RESOLVED_SOURCE_GIT_COMMIT:-$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)}" \
    "${LOOPX_PYTHON:-python3}" - <<'PY'
from pathlib import Path
import json
import os
import sys

link = Path(os.environ["LOOPX_VERIFY_LINK"])
release_dir = Path(os.environ["LOOPX_VERIFY_RELEASE_DIR"])
expected = (release_dir / "scripts" / "loopx").resolve()
try:
    actual = link.resolve(strict=True)
except OSError as exc:
    print(f"loopx installer error: default executable cannot be resolved: {exc}", file=sys.stderr)
    raise SystemExit(1)
if actual != expected:
    print(
        "loopx installer error: default executable changed before promotion verification",
        file=sys.stderr,
    )
    raise SystemExit(1)

manifest_path = release_dir / "release.json"
try:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"loopx installer error: release manifest is unreadable: {exc}", file=sys.stderr)
    raise SystemExit(1)
if manifest.get("release_id") != release_dir.name:
    print("loopx installer error: release manifest id does not match its directory", file=sys.stderr)
    raise SystemExit(1)

expected_commit = os.environ.get("LOOPX_VERIFY_SOURCE_COMMIT") or ""
source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
if expected_commit and source.get("git_commit") != expected_commit:
    print("loopx installer error: release manifest does not match the intended source commit", file=sys.stderr)
    raise SystemExit(1)
PY
}

validate_release_candidate() {
  local candidate="$1"
  local candidate_wrapper="$candidate/scripts/loopx"
  if [[ ! -x "$candidate_wrapper" ]]; then
    echo "loopx installer error: release candidate is missing an executable wrapper" >&2
    return 1
  fi

  local doctor_json
  if ! doctor_json="$(PATH="$candidate/scripts:$PATH" "$candidate_wrapper" --format json doctor --deep)"; then
    echo "loopx installer error: release candidate doctor validation failed" >&2
    return 1
  fi
  LOOPX_CANDIDATE_DOCTOR_JSON="$doctor_json" "${LOOPX_PYTHON:-python3}" - <<'PY'
import json
import os
import sys

try:
    payload = json.loads(os.environ["LOOPX_CANDIDATE_DOCTOR_JSON"])
except (KeyError, json.JSONDecodeError) as exc:
    print(f"loopx installer error: release candidate doctor output is invalid: {exc}", file=sys.stderr)
    raise SystemExit(1)

required_checks = {
    "command_package_same_root",
    "representative_cli_commands",
    "representative_cli_imports",
    "representative_package_paths",
}
checks = {
    str(item.get("id")): item
    for item in payload.get("checks", [])
    if isinstance(item, dict)
}
missing = sorted(required_checks - checks.keys())
failed = sorted(
    check_id
    for check_id in required_checks
    if not checks.get(check_id, {}).get("ok")
)
if payload.get("mode") != "deep" or not payload.get("ok") or missing or failed:
    print(
        "loopx installer error: release candidate is incomplete "
        f"(missing_checks={missing}, failed_checks={failed})",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
}

resolve_default_promotion() {
  case "$promote_default_request" in
    1|true|yes)
      promotion_mode="${LOOPX_PROMOTION_MODE:-explicit_override}"
      return 0
      ;;
    0|false|no)
      promotion_mode="canary_only_explicit"
      return 1
      ;;
    auto)
      ;;
    *)
      echo "loopx installer error: LOOPX_PROMOTE_DEFAULT must be auto, 1, or 0" >&2
      exit 2
      ;;
  esac

  if ! git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    promotion_mode="canary_only_unverified_source"
    return 1
  fi

  local source_commit approved_commit source_status approved_ref
  source_commit="$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || true)"
  source_status="$(git -C "$repo_root" status --porcelain 2>/dev/null || true)"
  approved_ref="${LOOPX_APPROVED_DEFAULT_REF:-refs/remotes/origin/main}"
  approved_commit="$(git -C "$repo_root" rev-parse "$approved_ref" 2>/dev/null || true)"
  if [[ -z "$approved_commit" ]]; then
    approved_commit="$(git -C "$repo_root" rev-parse refs/heads/main 2>/dev/null || true)"
  fi
  if [[ -n "$source_commit" && "$source_commit" == "$approved_commit" && -z "$source_status" ]]; then
    promotion_mode="trusted_main_auto"
    return 0
  fi

  promotion_mode="canary_only_untrusted_checkout"
  return 1
}

if [[ -z "$shell_profile" ]]; then
  case "${SHELL:-}" in
    */zsh) shell_profile="$HOME/.zshrc" ;;
    */bash) shell_profile="$HOME/.bashrc" ;;
    *) shell_profile="$HOME/.profile" ;;
  esac
fi

configure_python_runtime

promote_default=0
if resolve_default_promotion; then
  promote_default=1
fi

if [[ "$promote_default" == "0" ]]; then
  if [[ "$install_canary" == "0" ]]; then
    echo "loopx installer error: default promotion is guarded and LOOPX_INSTALL_CANARY=0 leaves no install target" >&2
    echo "Set LOOPX_PROMOTE_DEFAULT=1 only after explicitly approving this checkout." >&2
    exit 2
  fi
  mkdir -p "$bin_dir"
  chmod +x "$repo_root/scripts/loopx"
  install_symlink "$repo_root/scripts/loopx" "$bin_dir/loopx-canary"
  export PATH="$bin_dir:$PATH"
  "$bin_dir/loopx-canary" doctor >/dev/null
  cat <<EOF
loopx checkout installed as canary only
- default executable: unchanged
- canary executable: $bin_dir/loopx-canary
- promotion mode: $promotion_mode
- promote explicitly: LOOPX_PROMOTE_DEFAULT=1 $repo_root/scripts/install-local.sh

Current shell can use the canary with:
  export PATH="$bin_dir:\$PATH"
  loopx-canary doctor
EOF
  exit 0
fi

export LOOPX_PROMOTION_MODE="$promotion_mode"

mkdir -p "$releases_dir"
run_under_install_guard "$@"
warn_stale_promotion_readiness
acquire_install_lock
mkdir -p "$bin_dir"
disable_legacy_shim "goal-harness"
disable_legacy_shim "goal-harness-canary"
if [[ -z "$legacy_line" ]]; then
  legacy_line="- legacy command disabled: not present"
fi
reserve_release_id
copy_path "$repo_root/loopx" "$release_tmp/loopx"
copy_path "$repo_root/scripts" "$release_tmp/scripts"
copy_path "$repo_root/skills" "$release_tmp/skills"
copy_path "$repo_root/docs" "$release_tmp/docs"
copy_path "$repo_root/man" "$release_tmp/man"
copy_path "$repo_root/examples" "$release_tmp/examples"
copy_path "$repo_root/apps" "$release_tmp/apps"
copy_path "$repo_root/.github" "$release_tmp/.github"
copy_path "$repo_root/README.md" "$release_tmp/README.md"
copy_path "$repo_root/CONTRIBUTOR_TASKS.md" "$release_tmp/CONTRIBUTOR_TASKS.md"
copy_path "$repo_root/LICENSE" "$release_tmp/LICENSE"
copy_path "$repo_root/pyproject.toml" "$release_tmp/pyproject.toml"
printf '%s\n' "$LOOPX_PYTHON" >"$release_tmp/.loopx-python"
find "$release_tmp" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$release_tmp" -name '*.pyc' -type f -delete
if [[ -d "$release_tmp/apps" ]]; then
  find "$release_tmp/apps" \
    \( -name node_modules -o -name .next -o -name dist -o -name build -o -name coverage \) \
    -type d -prune -exec rm -rf {} +
fi
(
  cd "$release_tmp"
  PYTHONPATH="$release_tmp" "${LOOPX_PYTHON:-python3}" -m loopx.release_manifest \
    "$release_tmp" \
    --release-id "$release_id" \
    --source-root "$repo_root" \
    --installed-at "$installed_at"
)
chmod +x "$release_tmp/scripts/loopx"
mv "$release_tmp" "$release_dir"
release_tmp=""
if ! validate_release_candidate "$release_dir"; then
  rm -rf "$release_dir"
  exit 1
fi
install_symlink "$release_dir/scripts/loopx" "$bin_dir/loopx"
verify_default_promotion

canary_line="- canary executable: skipped"
if [[ "$install_canary" != "0" ]]; then
  chmod +x "$repo_root/scripts/loopx"
  install_symlink "$repo_root/scripts/loopx" "$bin_dir/loopx-canary"
  canary_line="- canary executable: $bin_dir/loopx-canary"
fi

if [[ -n "$shell_profile" ]]; then
  touch "$shell_profile"
  if ! grep -F "$bin_dir" "$shell_profile" >/dev/null 2>&1 \
    && ! grep -F '$HOME/.local/bin' "$shell_profile" >/dev/null 2>&1; then
    {
      printf '\n# LoopX local CLI\n'
      if [[ "$bin_dir" == "$HOME/.local/bin" ]]; then
        printf 'export PATH="$HOME/.local/bin:$PATH"\n'
      else
        printf 'export PATH="%s:$PATH"\n' "$bin_dir"
      fi
    } >>"$shell_profile"
  fi
  if ! grep -F "$man_root" "$shell_profile" >/dev/null 2>&1 \
    && ! grep -F '$HOME/.local/share/man' "$shell_profile" >/dev/null 2>&1; then
    {
      printf '\n# LoopX local manual\n'
      if [[ "$man_root" == "$HOME/.local/share/man" ]]; then
        printf 'export MANPATH="$HOME/.local/share/man:${MANPATH:-}"\n'
      else
        printf 'export MANPATH="%s:${MANPATH:-}"\n' "$man_root"
      fi
    } >>"$shell_profile"
  fi
fi

man_line="- manpage: skipped (source missing)"
man_source="$release_dir/man/loopx.1"
man_target="$man_dir/loopx.1.gz"
if [[ -f "$man_source" ]]; then
  mkdir -p "$man_dir"
  MAN_SOURCE="$man_source" MAN_TARGET="$man_target" "${LOOPX_PYTHON:-python3}" - <<'PY'
from pathlib import Path
import gzip
import os
import shutil

source = Path(os.environ["MAN_SOURCE"])
target = Path(os.environ["MAN_TARGET"])
target.parent.mkdir(parents=True, exist_ok=True)
with source.open("rb") as raw, gzip.open(target, "wb", compresslevel=9) as zipped:
    shutil.copyfileobj(raw, zipped)
PY
  chmod 0644 "$man_target"
  man_line="- manpage: $man_target"
fi

export PATH="$bin_dir:$PATH"
"$bin_dir/loopx" doctor >/dev/null
if [[ "$install_canary" != "0" ]]; then
  "$bin_dir/loopx-canary" doctor >/dev/null
fi

skill_line="- skill: skipped"
skills_source="$release_dir/skills"
if [[ "$install_skill" != "0" && -d "$skills_source" ]]; then
  mkdir -p "$skills_dir"
  skill_line=""
  while IFS= read -r skill_source; do
    skill_name="$(basename "$skill_source")"
    skill_target="$skills_dir/$skill_name"
    rm -rf "$skill_target"
    mkdir -p "$skill_target"
    cp -R "$skill_source"/. "$skill_target"/
    skill_line="${skill_line}- skill: $skill_target"$'\n'
  done < <(find "$skills_source" -mindepth 1 -maxdepth 1 -type d -print | sort)
  skill_line="${skill_line%$'\n'}"
fi

slash_line="- slash commands: skipped"
install_slash_commands="${LOOPX_INSTALL_SLASH_COMMANDS:-1}"
slash_surfaces="${LOOPX_INSTALL_SLASH_COMMAND_SURFACES:-all}"
if [[ "$install_slash_commands" != "0" ]]; then
  slash_args=(slash-commands --install)
  IFS=',' read -ra slash_surface_list <<<"$slash_surfaces"
  for slash_surface in "${slash_surface_list[@]}"; do
    if [[ -n "$slash_surface" ]]; then
      slash_args+=(--surface "$slash_surface")
    fi
  done
  if slash_json="$("$bin_dir/loopx" --format json "${slash_args[@]}" 2>/dev/null)"; then
    slash_line="$(LOOPX_SLASH_INSTALL_JSON="$slash_json" "${LOOPX_PYTHON:-python3}" - <<'PY'
import json
import os

payload = json.loads(os.environ["LOOPX_SLASH_INSTALL_JSON"])
summary = payload.get("summary") or {}
counts = summary.get("status_counts") or {}
count_text = ",".join(f"{key}={counts[key]}" for key in sorted(counts)) or "none"
parts = []
if summary.get("codex_prompt_dir"):
    parts.append(f"codex prompts: {summary['codex_prompt_dir']}")
if summary.get("codex_skill_dir"):
    parts.append(f"codex skills: {summary['codex_skill_dir']}")
if summary.get("claude_skill_dir"):
    parts.append(f"claude skills: {summary['claude_skill_dir']}")
if not parts:
    parts.append("no supported surfaces selected")
print(f"- slash commands: {'; '.join(parts)} ({count_text})")
PY
)"
  else
    slash_line="- slash commands: install attempted; run manually: loopx slash-commands --install"
  fi
fi

# loopx Claude Code adapter: OPT-IN, OFF by default — the normal loopx install
# does not install MCP, hooks, or settings. The lightweight slash-command
# skills above may write ~/.claude/skills so Claude Code can discover /loopx,
# while the run-loop adapter remains explicit. Enable the adapter with
# LOOPX_INSTALL_CLAUDE=1 (installs at USER scope: MCP + /loopx command). Add
# the optional should_run gate later with `install.py --scope <user|project>
# --harden`. Prefer PROJECT scope:
# `python <release>/loopx/claude_goal_mode/scripts/install.py --scope project`.
claude_installer="$release_dir/loopx/claude_goal_mode/scripts/install.py"
install_claude="${LOOPX_INSTALL_CLAUDE:-0}"
claude_line="- loopx Claude adapter: skipped (opt-in; LOOPX_INSTALL_CLAUDE=1, or run install.py --scope project|user)"
if [[ "$install_claude" != "0" && -f "$claude_installer" ]]; then
  if ! command -v claude >/dev/null 2>&1; then
    claude_line="- loopx Claude adapter: skipped (Claude Code not found on PATH)"
  else
    claude_python="${LOOPX_PYTHON:-python3}"
    command -v "$claude_python" >/dev/null 2>&1 || claude_python="python"
    if "$claude_python" "$claude_installer" --scope user >/dev/null 2>&1; then
      claude_line="- loopx Claude adapter: ~/.claude (MCP + /loopx, user scope; no hooks — add with --harden)"
    else
      claude_line="- loopx Claude adapter: install attempted; run manually: $claude_python \"$claude_installer\" --scope user"
    fi
  fi
fi

# loopx OpenCode goal bridge: OPT-IN, OFF by default. Static OpenCode commands
# remain part of the ordinary slash-command install; this flag additionally
# provisions the plugin, runtime, and pinned dependencies. The bridge wraps
# opencode-goal-plugin@0.6.5 and gates idle continuation plus timer wakes
# through LoopX quota should-run. Install manually with:
#   loopx slash-commands --install --surface opencode --with-goal-bridge
install_opencode="${LOOPX_INSTALL_OPENCODE:-0}"
opencode_line="- loopx OpenCode bridge: skipped (opt-in; LOOPX_INSTALL_OPENCODE=1, or run: loopx slash-commands --install --surface opencode --with-goal-bridge)"
if [[ "$install_opencode" != "0" ]]; then
  if "$bin_dir/loopx" slash-commands --install --surface opencode --with-goal-bridge >/dev/null 2>&1; then
    opencode_line="- loopx OpenCode bridge: ~/.config/opencode (commands, plugin, runtime, pinned deps; restart OpenCode after install)"
  else
    opencode_line="- loopx OpenCode bridge: install attempted; run manually: loopx slash-commands --install --surface opencode --with-goal-bridge"
  fi
fi

cat <<EOF
loopx installed locally
- executable: $bin_dir/loopx
- release: $release_dir
- promotion mode: $promotion_mode
- manual root: $man_root
$man_line
$canary_line
- executable compatibility: none
$legacy_line
- profile: $shell_profile
$skill_line
$slash_line
$claude_line
$opencode_line

Current shell can use it with:
  export PATH="$bin_dir:\$PATH"
  export MANPATH="$man_root:\${MANPATH:-}"
  loopx doctor
  man loopx
EOF
