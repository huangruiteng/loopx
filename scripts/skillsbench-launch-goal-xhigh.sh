#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/skillsbench-launch-goal-xhigh.sh [--dry-run] <task-id> [tag] [remote-proxy-port]

Launch one SkillsBench task through the host-local Codex CLI /goal route with
the command/file bridge. Environment-specific values are supplied by env vars.

Required env:
  SKILLSBENCH_SSH_DESTINATION          SSH destination for the remote runner
  SKILLSBENCH_REMOTE_ROOT              Remote LoopX checkout to run from
  SKILLSBENCH_ROOT                     Remote SkillsBench checkout/root
  SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD  Expected LoopX git head in remote root

Optional env:
  SKILLSBENCH_LOCAL_CODEX_PROXY_HOST   Local proxy host, default 127.0.0.1
  SKILLSBENCH_LOCAL_CODEX_PROXY_PORT   Local proxy port, default 18180
  SKILLSBENCH_ROUTE                    Route, default codex-cli-goal-baseline
  SKILLSBENCH_MODEL                    Model, default gpt-5.5
  SKILLSBENCH_REASONING_EFFORT         Reasoning effort, default xhigh
  SKILLSBENCH_BUILD_STALL_TIMEOUT_SEC  Setup stall timeout; 0 disables cap
  SKILLSBENCH_RUN_TIMEOUT_SEC          Supervisor timeout, default 28800
  SKILLSBENCH_GOAL_ID                  Local evidence goal id, default loopx-meta
  SKILLSBENCH_RUN_STAMP                Deterministic timestamp override
  SKILLSBENCH_SSH_OPTIONS              Extra ssh options, one shell word each
EOF
}

dry_run=false
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
  shift
fi

task_id="${1:-}"
if [[ -z "$task_id" ]]; then
  usage >&2
  exit 2
fi
tag="${2:-${SKILLSBENCH_RUN_TAG:-manual}}"
remote_proxy_port="${3:-${SKILLSBENCH_REMOTE_CODEX_PROXY_PORT:-18180}}"

required_env=(
  SKILLSBENCH_SSH_DESTINATION
  SKILLSBENCH_REMOTE_ROOT
  SKILLSBENCH_ROOT
  SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD
)
for key in "${required_env[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    echo "missing required env: ${key}" >&2
    exit 2
  fi
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

stamp="${SKILLSBENCH_RUN_STAMP:-$(date +%Y%m%dT%H%M%SCST)}"
safe_task="${task_id//[^A-Za-z0-9_ -]/-}"
safe_task="${safe_task// /-}"
safe_task="${safe_task//_/-}"

goal_id="${SKILLSBENCH_GOAL_ID:-loopx-meta}"
route="${SKILLSBENCH_ROUTE:-codex-cli-goal-baseline}"
model="${SKILLSBENCH_MODEL:-gpt-5.5}"
reasoning_effort="${SKILLSBENCH_REASONING_EFFORT:-xhigh}"
build_stall_timeout="${SKILLSBENCH_BUILD_STALL_TIMEOUT_SEC:-0}"
run_timeout="${SKILLSBENCH_RUN_TIMEOUT_SEC:-28800}"
local_proxy_host="${SKILLSBENCH_LOCAL_CODEX_PROXY_HOST:-127.0.0.1}"
local_proxy_port="${SKILLSBENCH_LOCAL_CODEX_PROXY_PORT:-18180}"

run_group="skillsbench-codex-cli-goal-xhigh-${safe_task}-${tag}-${stamp}"
job_name="${safe_task}__codex_cli_goal_xhigh_${tag}_${stamp}"

public_dir=".local/goals/${goal_id}/skillsbench-runs/${run_group}"
private_dir=".local/goals/${goal_id}/private/skillsbench-runs/${run_group}"
mkdir -p "$public_dir" "$private_dir"

remote_command=$(
  printf 'cd %q && python3 scripts/skillsbench_automation_loop.py ' \
    "$SKILLSBENCH_REMOTE_ROOT"
  printf '%q ' \
    --skillsbench-root "$SKILLSBENCH_ROOT" \
    --expected-loopx-git-head "$SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD" \
    --task-id "$task_id" \
    --route "$route" \
    --model "$model" \
    --reasoning-effort "$reasoning_effort" \
    --build-stall-timeout-sec "$build_stall_timeout" \
    --codex-api-egress-mode reverse-tunnel \
    --codex-api-reverse-tunnel-proxy "http://127.0.0.1:${remote_proxy_port}" \
    --host-local-acp-launch \
    --remote-command-file-bridge-probe \
    --run-group-id "$run_group" \
    --job-name "$job_name" \
    --update-ledger \
    --append-history
)

ssh_options=(--ssh-option ConnectTimeout=10)
if [[ -n "${SKILLSBENCH_SSH_OPTIONS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_ssh_options=(${SKILLSBENCH_SSH_OPTIONS})
  for option in "${extra_ssh_options[@]}"; do
    ssh_options+=(--ssh-option "$option")
  done
fi

supervisor_cmd=(
  python3
  scripts/skillsbench_reverse_tunnel_supervisor.py
  --ssh-destination "$SKILLSBENCH_SSH_DESTINATION"
  "${ssh_options[@]}"
  --cleanup-stale-local-forward
  --remote-forward "127.0.0.1:${remote_proxy_port}:${local_proxy_host}:${local_proxy_port}"
  --run-timeout-sec "$run_timeout"
  --remote-command "$remote_command"
  --private-log-path "${private_dir}/remote-command.log"
  --public-output-path "${public_dir}/supervisor.public.json"
)

if [[ "$dry_run" == "true" ]]; then
  printf 'dry_run=true\n'
  printf 'task_id=%s\n' "$task_id"
  printf 'run_group=%s\n' "$run_group"
  printf 'job_name=%s\n' "$job_name"
  printf 'public_output=%s/supervisor.public.json\n' "$public_dir"
  printf 'private_dir=%s\n' "$private_dir"
  printf 'remote_proxy_port=%s\n' "$remote_proxy_port"
  printf 'remote_command=%s\n' "$remote_command"
  printf 'supervisor_command='
  printf '%q ' "${supervisor_cmd[@]}"
  printf '\n'
  exit 0
fi

pid="$(
  python3 - "$private_dir" "${supervisor_cmd[@]}" <<'PY'
import subprocess
import sys
from pathlib import Path

private_dir = Path(sys.argv[1])
cmd = sys.argv[2:]
stdout = open(private_dir / "supervisor.stdout", "ab", buffering=0)
stderr = open(private_dir / "supervisor.stderr", "ab", buffering=0)
proc = subprocess.Popen(
    cmd,
    stdin=subprocess.DEVNULL,
    stdout=stdout,
    stderr=stderr,
    start_new_session=True,
    close_fds=True,
)
print(proc.pid)
PY
)"

cat <<EOF
pid=${pid}
task_id=${task_id}
run_group=${run_group}
job_name=${job_name}
public_output=${public_dir}/supervisor.public.json
private_dir=${private_dir}
remote_proxy_port=${remote_proxy_port}
EOF
