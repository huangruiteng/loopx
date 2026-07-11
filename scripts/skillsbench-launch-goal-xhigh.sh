#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/skillsbench-launch-goal-xhigh.sh [--dry-run] <task-id[,task-id...]> [tag] [remote-proxy-port]

Launch one or more SkillsBench tasks through one host-local Codex CLI /goal
batch with a shared reverse tunnel. Environment-specific values use env vars.

Required env:
  SKILLSBENCH_SSH_DESTINATION          SSH destination for the remote runner
  SKILLSBENCH_REMOTE_ROOT              Remote LoopX checkout to run from
  SKILLSBENCH_ROOT                     Remote SkillsBench checkout/root
  SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD  Expected LoopX git head in remote root

Optional env:
  SKILLSBENCH_LOCAL_CODEX_PROXY_HOST   Local proxy host, default 127.0.0.1
  SKILLSBENCH_LOCAL_CODEX_PROXY_PORT   Local proxy port, default 18180
  SKILLSBENCH_DOCKER_PROXY_HOST        Remote Docker bridge host for benchmark
                                       setup/verifier egress; default auto
  SKILLSBENCH_DOCKER_API_VERSION       Remote Docker daemon API version passed
                                       to Docker CLI/Compose; default auto
  SKILLSBENCH_ROUTE                    Route, default codex-cli-goal-baseline
  SKILLSBENCH_MODEL                    Model, default gpt-5.5
  SKILLSBENCH_REASONING_EFFORT         Reasoning effort, default xhigh
  SKILLSBENCH_REMOTE_CODEX_BIN          Codex CLI executable on remote runner;
                                       default codex from remote PATH
  SKILLSBENCH_LOCAL_CODEX_SANDBOX      Host Codex sandbox mode; default
                                       workspace-write
  SKILLSBENCH_BUILD_STALL_TIMEOUT_SEC  Setup stall timeout, default 3600;
                                       0 disables cap
  SKILLSBENCH_RUN_TIMEOUT_SEC          Supervisor timeout, default 28800
  SKILLSBENCH_TUNNEL_PROBE_TIMEOUT_SEC Reverse-tunnel CONNECT probe timeout,
                                       default 20
  SKILLSBENCH_TUNNEL_READY_TIMEOUT_SEC Reverse-tunnel readiness budget,
                                       default 60
  SKILLSBENCH_PARALLEL_CASES           Batch concurrency, default 3
  SKILLSBENCH_BATCH_CASE_START_GAP_SEC Delay between case starts, default 3
  SKILLSBENCH_GOAL_ID                  Local evidence goal id, default loopx-meta
  SKILLSBENCH_RUN_STAMP                Deterministic timestamp override
  SKILLSBENCH_SSH_OPTIONS              Extra ssh options, one shell word each
  SKILLSBENCH_APPEND_HISTORY           Set to 1 to append LoopX history
  SKILLSBENCH_REGISTRY                 Optional registry path for history append
  SKILLSBENCH_LOCAL_RUN_LEDGER_PATH    Local private live ledger; default below
                                       the goal's skillsbench-ledgers directory
  SKILLSBENCH_LOCAL_RUN_LEDGER_SEED    Optional accepted-lane ledger copied
                                       when the live ledger does not exist yet;
                                       keep unrelated benchmark lanes out
  SKILLSBENCH_LEDGER_CATCHUP_GROUP     Optional run-group substring used for
                                       local ledger catch-up. Canonical runs
                                       default to the Goal campaign prefix;
                                       isolated ledgers default to this run.
  SKILLSBENCH_CANONICAL_CASE_IDS_FILE  Optional canonical case-id file; enables
                                       standard aggregate refresh after closeout
  SKILLSBENCH_STANDARD_AGGREGATE_PATH  Aggregate output path; default beside
                                       the local live ledger; requires an
                                       explicit local ledger when set
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

task_ids_raw="${1:-}"
if [[ -z "$task_ids_raw" ]]; then
  usage >&2
  exit 2
fi
task_ids_normalized="${task_ids_raw//,/ }"
read -r -a task_ids <<<"$task_ids_normalized"
if ((${#task_ids[@]} == 0)); then
  usage >&2
  exit 2
fi
task_id="${task_ids[0]}"
task_count="${#task_ids[@]}"
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
if [[ -n "${SKILLSBENCH_STANDARD_AGGREGATE_PATH:-}" ]] &&
  [[ -z "${SKILLSBENCH_LOCAL_RUN_LEDGER_PATH:-}" ]]; then
  echo "SKILLSBENCH_STANDARD_AGGREGATE_PATH requires SKILLSBENCH_LOCAL_RUN_LEDGER_PATH" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

ssh_command_options=(-o BatchMode=yes -o ConnectTimeout=10)
ssh_options=(--ssh-option ConnectTimeout=10)
if [[ -n "${SKILLSBENCH_SSH_OPTIONS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_ssh_options=(${SKILLSBENCH_SSH_OPTIONS})
  for option in "${extra_ssh_options[@]}"; do
    ssh_command_options+=(-o "$option")
    ssh_options+=(--ssh-option "$option")
  done
fi

remote_codex_bin="${SKILLSBENCH_REMOTE_CODEX_BIN:-codex}"
local_codex_sandbox="${SKILLSBENCH_LOCAL_CODEX_SANDBOX:-workspace-write}"
remote_codex_bin_mode="path_lookup"
if [[ -n "${SKILLSBENCH_REMOTE_CODEX_BIN:-}" ]]; then
  remote_codex_bin_mode="explicit"
fi
if [[ "$dry_run" == "false" ]]; then
  if [[ "$remote_codex_bin" == */* ]]; then
    printf -v remote_codex_probe \
      'test -x %q && %q --version >/dev/null 2>&1' \
      "$remote_codex_bin" "$remote_codex_bin"
  else
    printf -v remote_codex_probe \
      'command -v %q >/dev/null 2>&1 && %q --version >/dev/null 2>&1' \
      "$remote_codex_bin" "$remote_codex_bin"
  fi
  if ! ssh "${ssh_command_options[@]}" "$SKILLSBENCH_SSH_DESTINATION" \
    "$remote_codex_probe"; then
    echo "remote Codex CLI unavailable; set SKILLSBENCH_REMOTE_CODEX_BIN" >&2
    exit 2
  fi
fi

stamp="${SKILLSBENCH_RUN_STAMP:-$(date +%Y%m%dT%H%M%SCST)}"
safe_task="${task_id//[^A-Za-z0-9_ -]/-}"
safe_task="${safe_task// /-}"
safe_task="${safe_task//_/-}"
if ((task_count > 1)); then
  safe_task="batch-${task_count}"
fi

goal_id="${SKILLSBENCH_GOAL_ID:-loopx-meta}"
local_run_ledger="${SKILLSBENCH_LOCAL_RUN_LEDGER_PATH:-.local/goals/${goal_id}/skillsbench-ledgers/live-standard-run-ledger.json}"
route="${SKILLSBENCH_ROUTE:-codex-cli-goal-baseline}"
model="${SKILLSBENCH_MODEL:-gpt-5.5}"
reasoning_effort="${SKILLSBENCH_REASONING_EFFORT:-xhigh}"
build_stall_timeout="${SKILLSBENCH_BUILD_STALL_TIMEOUT_SEC:-3600}"
run_timeout="${SKILLSBENCH_RUN_TIMEOUT_SEC:-28800}"
tunnel_probe_timeout="${SKILLSBENCH_TUNNEL_PROBE_TIMEOUT_SEC:-20}"
tunnel_ready_timeout="${SKILLSBENCH_TUNNEL_READY_TIMEOUT_SEC:-60}"
parallel_cases="${SKILLSBENCH_PARALLEL_CASES:-3}"
if ((parallel_cases > task_count)); then
  parallel_cases="$task_count"
fi
batch_case_start_gap="${SKILLSBENCH_BATCH_CASE_START_GAP_SEC:-3}"
local_proxy_host="${SKILLSBENCH_LOCAL_CODEX_PROXY_HOST:-127.0.0.1}"
local_proxy_port="${SKILLSBENCH_LOCAL_CODEX_PROXY_PORT:-18180}"
docker_api_version="${SKILLSBENCH_DOCKER_API_VERSION:-auto}"
if [[ -z "$docker_api_version" || "$docker_api_version" == "auto" ]]; then
  docker_api_probe_py='import json, sys; print(json.load(sys.stdin)["ApiVersion"])'
  printf -v docker_api_probe_command \
    'curl --silent --show-error --fail --unix-socket /var/run/docker.sock http://localhost/version | python3 -c %q' \
    "$docker_api_probe_py"
  docker_api_version="$(
    ssh "${ssh_command_options[@]}" "$SKILLSBENCH_SSH_DESTINATION" \
      "$docker_api_probe_command"
  )"
fi
if [[ ! "$docker_api_version" =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "invalid remote Docker API version; set SKILLSBENCH_DOCKER_API_VERSION" >&2
  exit 2
fi
docker_proxy_host="${SKILLSBENCH_DOCKER_PROXY_HOST:-auto}"
docker_proxy_listen_host="$docker_proxy_host"
docker_proxy_allowed_peer=""
docker_proxy_endpoint_mode="explicit"
if [[ -z "$docker_proxy_host" || "$docker_proxy_host" == "auto" ]]; then
  docker_security_options="$(
    ssh "${ssh_command_options[@]}" "$SKILLSBENCH_SSH_DESTINATION" \
      "DOCKER_API_VERSION=${docker_api_version} docker info --format '{{json .SecurityOptions}}' 2>/dev/null"
  )"
  if [[ "$docker_security_options" == *'name=rootless'* ]]; then
    docker_proxy_host="$(
      ssh "${ssh_command_options[@]}" "$SKILLSBENCH_SSH_DESTINATION" \
        'set -- $(hostname -I); printf "%s\n" "$1"'
    )"
    docker_proxy_listen_host="$docker_proxy_host"
    docker_proxy_allowed_peer="$docker_proxy_host"
    docker_proxy_endpoint_mode="rootless_host_interface"
  else
    docker_proxy_host="$(
      ssh "${ssh_command_options[@]}" "$SKILLSBENCH_SSH_DESTINATION" \
        "ip -4 addr show docker0 2>/dev/null | awk '/inet /{print \$2}' | cut -d/ -f1 | head -n1"
    )"
    docker_proxy_listen_host="$docker_proxy_host"
    docker_proxy_endpoint_mode="docker_bridge"
  fi
  if [[ -z "$docker_proxy_host" ]]; then
    echo "missing remote Docker proxy host; set SKILLSBENCH_DOCKER_PROXY_HOST" >&2
    exit 2
  fi
fi
bridge_proxy_url="http://${docker_proxy_host}:${remote_proxy_port}"
loopback_proxy_url="http://127.0.0.1:${remote_proxy_port}"
bridge_forwarder_py='import select, socket, sys, threading
listen_host = sys.argv[1]
listen_port = int(sys.argv[2])
allowed_peer = sys.argv[3]
target = ("127.0.0.1", listen_port)

def pipe(a, b):
    sockets = [a, b]
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                return
            for src in readable:
                data = src.recv(65536)
                if not data:
                    return
                (b if src is a else a).sendall(data)
    finally:
        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((listen_host, listen_port))
server.listen(64)
while True:
    client, addr = server.accept()
    if allowed_peer and addr[0] != allowed_peer:
        client.close()
        continue
    upstream = socket.create_connection(target)
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
'
extra_runner_args=()
if [[ -n "${SKILLSBENCH_REGISTRY:-}" ]]; then
  extra_runner_args+=(--registry "$SKILLSBENCH_REGISTRY")
fi
if ((task_count > 1)); then
  task_ids_csv="$(IFS=,; printf '%s' "${task_ids[*]}")"
  extra_runner_args+=(
    --task-ids "$task_ids_csv"
    --parallel-cases "$parallel_cases"
    --batch-case-start-gap-sec "$batch_case_start_gap"
  )
else
  extra_runner_args+=(--task-id "$task_id")
fi
if [[ "${SKILLSBENCH_APPEND_HISTORY:-0}" == "1" ]]; then
  extra_runner_args+=(--append-history)
fi

run_group="skillsbench-codex-cli-goal-xhigh-${safe_task}-${tag}-${stamp}"
job_name="${safe_task}__codex_cli_goal_xhigh_${tag}_${stamp}"
if [[ -n "${SKILLSBENCH_LEDGER_CATCHUP_GROUP:-}" ]]; then
  ledger_catchup_group="$SKILLSBENCH_LEDGER_CATCHUP_GROUP"
elif [[ -n "${SKILLSBENCH_CANONICAL_CASE_IDS_FILE:-}" ]]; then
  ledger_catchup_group="skillsbench-codex-cli-goal-xhigh-"
else
  ledger_catchup_group="$run_group"
fi

public_root=".local/goals/${goal_id}/skillsbench-runs"
public_dir="${public_root}/${run_group}"
private_dir=".local/goals/${goal_id}/private/skillsbench-runs/${run_group}"
mkdir -p "$public_dir" "$private_dir"

remote_command=$(
  printf 'cd %q || exit 1; ' \
    "$SKILLSBENCH_REMOTE_ROOT"
  printf 'python3 -c %q %q %q %q & ' \
    "$bridge_forwarder_py" "$docker_proxy_listen_host" "$remote_proxy_port" \
    "$docker_proxy_allowed_peer"
  printf 'loopx_benchmark_proxy_forwarder_pid=$!; '
  printf 'trap %q EXIT; ' 'kill "$loopx_benchmark_proxy_forwarder_pid" 2>/dev/null || true'
  printf 'sleep 0.5; '
  printf '%q ' \
    "LOOPX_SKILLSBENCH_EGRESS_PROXY=${bridge_proxy_url}" \
    "DOCKER_API_VERSION=${docker_api_version}" \
    python3 \
    scripts/skillsbench_automation_loop.py
  printf '%q ' \
    --skillsbench-root "$SKILLSBENCH_ROOT" \
    --expected-loopx-git-head "$SKILLSBENCH_EXPECTED_LOOPX_GIT_HEAD" \
    --route "$route" \
    --model "$model" \
    --reasoning-effort "$reasoning_effort" \
    --build-stall-timeout-sec "$build_stall_timeout" \
    --codex-api-egress-mode reverse-tunnel \
    --codex-api-reverse-tunnel-proxy "$loopback_proxy_url" \
    --benchmark-egress-proxy-mode require \
    --host-local-acp-launch \
    --local-codex-bin "$remote_codex_bin" \
    --local-codex-sandbox "$local_codex_sandbox" \
    --remote-command-file-bridge-probe \
    --run-group-id "$run_group" \
    --job-name "$job_name"
  if ((${#extra_runner_args[@]})); then
    printf '%q ' "${extra_runner_args[@]}"
  fi
)

supervisor_cmd=(
  python3
  scripts/skillsbench_reverse_tunnel_supervisor.py
  --ssh-destination "$SKILLSBENCH_SSH_DESTINATION"
  "${ssh_options[@]}"
  --cleanup-stale-local-forward
  --remote-forward "127.0.0.1:${remote_proxy_port}:${local_proxy_host}:${local_proxy_port}"
  --probe-timeout-sec "$tunnel_probe_timeout"
  --tunnel-ready-timeout-sec "$tunnel_ready_timeout"
  --run-timeout-sec "$run_timeout"
  --remote-failure-cleanup-pattern "$job_name"
  --remote-failure-cleanup-include-docker
  --remote-command "$remote_command"
  --remote-public-artifact-root "${SKILLSBENCH_REMOTE_ROOT}/.local/private-benchmark-jobs"
  --remote-public-artifact-glob "${job_name}*/runner_prerequisites.public.json"
  --remote-public-artifact-glob "${job_name}*/loopx_controller_trace.public.json"
  --remote-public-artifact-glob "${job_name}*/runner_config.public.json"
  --remote-public-artifact-glob "${job_name}*/*/benchmark_run.compact.json"
  --remote-public-artifact-glob "${job_name}*/host_local_acp_relay_traces/*.compact.json"
  --local-public-artifact-dir "$public_dir"
  --local-run-ledger-path "$local_run_ledger"
  --local-run-group-id "$run_group"
  --local-ledger-catchup-root "$public_root"
  --local-ledger-catchup-run-group-contains "$ledger_catchup_group"
  --private-log-path "${private_dir}/remote-command.log"
  --public-output-path "${public_dir}/supervisor.public.json"
)

if [[ "$dry_run" == "false" && ! -f "$local_run_ledger" && -n "${SKILLSBENCH_LOCAL_RUN_LEDGER_SEED:-}" ]]; then
  mkdir -p "$(dirname "$local_run_ledger")"
  cp "$SKILLSBENCH_LOCAL_RUN_LEDGER_SEED" "$local_run_ledger"
fi
if [[ -n "${SKILLSBENCH_CANONICAL_CASE_IDS_FILE:-}" ]]; then
  standard_aggregate="${SKILLSBENCH_STANDARD_AGGREGATE_PATH:-$(dirname "$local_run_ledger")/standard-current-aggregate.json}"
  supervisor_cmd+=(
    --local-current-aggregate-path "$standard_aggregate"
    --local-canonical-case-ids-file "$SKILLSBENCH_CANONICAL_CASE_IDS_FILE"
    --local-target-lane-id codex-cli-goal-xhigh
  )
fi

if [[ "$dry_run" == "true" ]]; then
  printf 'dry_run=true\n'
  printf 'task_ids=%s\n' "$(IFS=,; printf '%s' "${task_ids[*]}")"
  printf 'parallel_cases=%s\n' "$parallel_cases"
  printf 'run_group=%s\n' "$run_group"
  printf 'job_name=%s\n' "$job_name"
  printf 'public_output=%s/supervisor.public.json\n' "$public_dir"
  printf 'private_dir=%s\n' "$private_dir"
  printf 'remote_proxy_port=%s\n' "$remote_proxy_port"
  printf 'docker_proxy_host=%s\n' "$docker_proxy_host"
  printf 'docker_proxy_endpoint_mode=%s\n' "$docker_proxy_endpoint_mode"
  printf 'docker_api_version=%s\n' "$docker_api_version"
  printf 'remote_codex_bin_mode=%s\n' "$remote_codex_bin_mode"
  printf 'local_codex_sandbox=%s\n' "$local_codex_sandbox"
  printf 'local_run_ledger=%s\n' "$local_run_ledger"
  if [[ -n "${standard_aggregate:-}" ]]; then
    printf 'standard_aggregate=%s\n' "$standard_aggregate"
  fi
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
task_ids=$(IFS=,; printf '%s' "${task_ids[*]}")
parallel_cases=${parallel_cases}
run_group=${run_group}
job_name=${job_name}
public_output=${public_dir}/supervisor.public.json
private_dir=${private_dir}
remote_proxy_port=${remote_proxy_port}
docker_proxy_host=${docker_proxy_host}
docker_proxy_endpoint_mode=${docker_proxy_endpoint_mode}
docker_api_version=${docker_api_version}
remote_codex_bin_mode=${remote_codex_bin_mode}
local_codex_sandbox=${local_codex_sandbox}
EOF
