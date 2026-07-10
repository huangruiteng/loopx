#!/usr/bin/env bash
set -euo pipefail

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
releases_dir="${LOOPX_RELEASES_DIR:-$HOME/.local/share/loopx/releases}"
release_id="${LOOPX_RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
release_dir="$releases_dir/$release_id"
release_tmp="$release_dir.tmp.$$"
legacy_line=""
installed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

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
  if [[ -e "$link" || -L "$link" ]]; then
    if [[ ! -L "$link" && -d "$link" ]]; then
      echo "loopx installer error: $link is a directory; remove it before installing" >&2
      return 1
    fi
    rm -f "$link"
  fi
  ln -s "$target" "$tmp"
  mv -f "$tmp" "$link"
}

if [[ -z "$shell_profile" ]]; then
  case "${SHELL:-}" in
    */zsh) shell_profile="$HOME/.zshrc" ;;
    */bash) shell_profile="$HOME/.bashrc" ;;
    *) shell_profile="$HOME/.profile" ;;
  esac
fi

warn_stale_promotion_readiness

mkdir -p "$bin_dir"
disable_legacy_shim "goal-harness"
disable_legacy_shim "goal-harness-canary"
if [[ -z "$legacy_line" ]]; then
  legacy_line="- legacy command disabled: not present"
fi
mkdir -p "$releases_dir"
rm -rf "$release_tmp"
mkdir -p "$release_tmp"
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
if [[ -e "$release_dir" ]]; then
  rm -rf "$release_tmp"
else
  mv "$release_tmp" "$release_dir"
fi
install_symlink "$release_dir/scripts/loopx" "$bin_dir/loopx"

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

cat <<EOF
loopx installed locally
- executable: $bin_dir/loopx
- release: $release_dir
- manual root: $man_root
$man_line
$canary_line
- executable compatibility: none
$legacy_line
- profile: $shell_profile
$skill_line
$slash_line
$claude_line

Current shell can use it with:
  export PATH="$bin_dir:\$PATH"
  export MANPATH="$man_root:\${MANPATH:-}"
  loopx doctor
  man loopx
EOF
