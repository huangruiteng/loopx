#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${LOOPX_REPO_ROOT:-$(cd "$script_dir/.." && pwd)}"
dashboard_dir="${LOOPX_DASHBOARD_DIR:-$repo_root/apps/dashboard}"
dashboard_dist_dir="${LOOPX_DASHBOARD_DIST_DIR:-$dashboard_dir/dist}"
bin_dir="${LOOPX_BIN_DIR:-$HOME/.local/bin}"
registry="${LOOPX_GLOBAL_REGISTRY:-$HOME/.codex/loopx/registry.global.json}"
status_port="${LOOPX_STATUS_PORT:-8766}"
status_limit="${LOOPX_STATUS_LIMIT:-80}"
status_contract_min_version="${LOOPX_STATUS_CONTRACT_MIN_VERSION:-2}"
dashboard_port="${LOOPX_DASHBOARD_PORT:-5174}"
host="${LOOPX_DASHBOARD_HOST:-127.0.0.1}"
label_prefix="${LOOPX_LAUNCH_LABEL_PREFIX:-com.loopx}"

uid="$(id -u)"
launch_agents_dir="$HOME/Library/LaunchAgents"
logs_dir="$HOME/Library/Logs/loopx"
status_label="$label_prefix.status"
dashboard_label="$label_prefix.dashboard"
status_plist="$launch_agents_dir/$status_label.plist"
dashboard_plist="$launch_agents_dir/$dashboard_label.plist"
control_plane_write_api_enabled=false

usage() {
  cat <<EOF
Usage: $0 [--enable-control-plane-write-api] install|uninstall|start|stop|restart|status

Installs user-level macOS LaunchAgents for:
  - LoopX global status feed: http://$host:$status_port/status.json
  - LoopX dashboard:          http://$host:$dashboard_port/

Default mode is read-only for control-plane settings. Pass
--enable-control-plane-write-api with install or restart to write that explicit
opt-in flag into the status LaunchAgent plist.

Environment overrides:
  LOOPX_REPO_ROOT
  LOOPX_DASHBOARD_DIR
  LOOPX_DASHBOARD_DIST_DIR
  LOOPX_BIN_DIR
  LOOPX_GLOBAL_REGISTRY
  LOOPX_STATUS_PORT
  LOOPX_STATUS_LIMIT
  LOOPX_STATUS_CONTRACT_MIN_VERSION
  LOOPX_DASHBOARD_PORT
  LOOPX_DASHBOARD_HOST
  LOOPX_LAUNCH_LABEL_PREFIX
EOF
}

xml_escape() {
  sed \
    -e 's/&/\&amp;/g' \
    -e 's/</\&lt;/g' \
    -e 's/>/\&gt;/g' \
    -e 's/"/\&quot;/g' \
    <<<"$1"
}

require_macos() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "macOS LaunchAgent installation requires Darwin/macOS." >&2
    exit 1
  fi
}

resolve_status_command() {
  if [[ -x "$bin_dir/loopx-canary" ]]; then
    printf '%s\n' "$bin_dir/loopx-canary"
  elif [[ -x "$bin_dir/loopx" ]]; then
    printf '%s\n' "$bin_dir/loopx"
  elif command -v loopx-canary >/dev/null 2>&1; then
    command -v loopx-canary
  elif command -v loopx >/dev/null 2>&1; then
    command -v loopx
  else
    echo "loopx is not installed; run scripts/install-local.sh first." >&2
    exit 1
  fi
}

resolve_python_command() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif [[ -x /usr/bin/python3 ]]; then
    printf '%s\n' /usr/bin/python3
  else
    echo "python3 is not on PATH; install Python 3 or add it to PATH." >&2
    exit 1
  fi
}

check_inputs() {
  [[ -d "$dashboard_dir" ]] || {
    echo "Dashboard directory not found: $dashboard_dir" >&2
    exit 1
  }
  [[ -f "$dashboard_dist_dir/index.html" ]] || {
    echo "Dashboard dist is missing; run a dashboard build before installing the LaunchAgent." >&2
    exit 1
  }
}

write_plists() {
  local status_command python_command path_prefix status_shell dashboard_shell control_plane_write_arg
  status_command="$(resolve_status_command)"
  python_command="$(resolve_python_command)"
  path_prefix="$bin_dir:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
  control_plane_write_arg=""
  if [[ "$control_plane_write_api_enabled" == "true" ]]; then
    control_plane_write_arg=" --enable-control-plane-write-api"
  fi
  status_shell="export PATH=\"$(xml_escape "$path_prefix"):\$PATH\"; exec \"$(xml_escape "$status_command")\" --registry \"$(xml_escape "$registry")\" serve-status --global-registry --host \"$(xml_escape "$host")\" --port \"$(xml_escape "$status_port")\" --limit \"$(xml_escape "$status_limit")\"$control_plane_write_arg"
  dashboard_shell="export PATH=\"$(xml_escape "$path_prefix"):\$PATH\"; exec \"$(xml_escape "$python_command")\" -m http.server \"$(xml_escape "$dashboard_port")\" --bind \"$(xml_escape "$host")\" --directory \"$(xml_escape "$dashboard_dist_dir")\""

  mkdir -p "$launch_agents_dir" "$logs_dir"

  cat >"$status_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$status_label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>$status_shell</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>$logs_dir/status.out.log</string>
  <key>StandardErrorPath</key>
  <string>$logs_dir/status.err.log</string>
</dict>
</plist>
EOF

  cat >"$dashboard_plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$dashboard_label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>$dashboard_shell</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>$logs_dir/dashboard.out.log</string>
  <key>StandardErrorPath</key>
  <string>$logs_dir/dashboard.err.log</string>
</dict>
</plist>
EOF
}

bootout_one() {
  local label="$1" plist="$2"
  launchctl bootout "gui/$uid" "$plist" >/dev/null 2>&1 || true
  launchctl bootout "gui/$uid/$label" >/dev/null 2>&1 || true
}

bootstrap_one() {
  local label="$1" plist="$2"
  bootout_one "$label" "$plist"
  launchctl bootstrap "gui/$uid" "$plist"
  launchctl kickstart -k "gui/$uid/$label"
}

start_agents() {
  bootstrap_one "$status_label" "$status_plist"
  bootstrap_one "$dashboard_label" "$dashboard_plist"
}

stop_agents() {
  bootout_one "$dashboard_label" "$dashboard_plist"
  bootout_one "$status_label" "$status_plist"
}

print_status_contract_health() {
  local status_url python_command status_json version producer control_plane_write
  status_url="http://$host:$status_port/status.json"
  python_command="$(resolve_python_command 2>/dev/null || true)"
  if ! command -v curl >/dev/null 2>&1 || [[ -z "$python_command" ]]; then
    echo "- status_contract: unknown (curl or python3 unavailable)"
    echo "- control_plane_write_api: unknown"
    return
  fi
  status_json="$(curl -fsS "$status_url" 2>/dev/null || true)"
  if [[ -z "$status_json" ]]; then
    echo "- status_contract: unavailable (status feed not reachable)"
    echo "- control_plane_write_api: unknown"
    return
  fi
  version="$("$python_command" -c 'import json,sys; data=json.load(sys.stdin); contract=data.get("status_contract") or {}; print(contract.get("schema_version", 0))' <<<"$status_json" 2>/dev/null || true)"
  producer="$("$python_command" -c 'import json,sys; data=json.load(sys.stdin); contract=data.get("status_contract") or {}; print(contract.get("producer") or "unknown")' <<<"$status_json" 2>/dev/null || true)"
  control_plane_write="$("$python_command" -c 'import json,sys; data=json.load(sys.stdin); api=data.get("local_dashboard_api") or {}; print("enabled" if api.get("control_plane_write_enabled") else "disabled")' <<<"$status_json" 2>/dev/null || true)"
  version="${version:-0}"
  producer="${producer:-unknown}"
  control_plane_write="${control_plane_write:-unknown}"
  echo "- status_contract: schema_version=$version producer=$producer expected>=$status_contract_min_version"
  echo "- control_plane_write_api: $control_plane_write"
  if [[ "$control_plane_write" == "enabled" ]]; then
    echo "  warning: control-plane registry writes are enabled for this local status feed"
  fi
  if [[ "$version" =~ ^[0-9]+$ ]] && (( version < status_contract_min_version )); then
    echo "  warning: status feed is using an old contract; run: $0 restart"
  fi
}

print_status() {
  echo "LaunchAgents:"
  launchctl print "gui/$uid/$status_label" >/dev/null 2>&1 \
    && echo "- $status_label: loaded" \
    || echo "- $status_label: not loaded"
  launchctl print "gui/$uid/$dashboard_label" >/dev/null 2>&1 \
    && echo "- $dashboard_label: loaded" \
    || echo "- $dashboard_label: not loaded"
  echo
  echo "URLs:"
  echo "- dashboard: http://$host:$dashboard_port/"
  echo "- status:    http://$host:$status_port/status.json"
  print_status_contract_health
  echo
  echo "Logs:"
  echo "- $logs_dir/status.out.log"
  echo "- $logs_dir/status.err.log"
  echo "- $logs_dir/dashboard.out.log"
  echo "- $logs_dir/dashboard.err.log"
}

main() {
  require_macos
  case "${1:-}" in
    install)
      check_inputs
      write_plists
      start_agents
      print_status
      ;;
    uninstall)
      stop_agents
      rm -f "$status_plist" "$dashboard_plist"
      print_status
      ;;
    start)
      [[ -f "$status_plist" && -f "$dashboard_plist" ]] || {
        echo "LaunchAgents are not installed; run: $0 install" >&2
        exit 1
      }
      start_agents
      print_status
      ;;
    stop)
      stop_agents
      print_status
      ;;
    restart)
      check_inputs
      write_plists
      start_agents
      print_status
      ;;
    status)
      print_status
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

parsed_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --enable-control-plane-write-api)
      control_plane_write_api_enabled=true
      shift
      ;;
    --)
      shift
      parsed_args+=("$@")
      break
      ;;
    *)
      parsed_args+=("$1")
      shift
      ;;
  esac
done

main "${parsed_args[@]}"
