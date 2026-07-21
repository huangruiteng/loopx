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
  SKILLSBENCH_RUNNER_PROFILE           Owner-only local JSON profile captured
                                       by skillsbench_runner_profile; explicit
                                       env values override profile values. If
                                       unset, the owner-local default is used
                                       when present. Capture the default with:
                                       python3 -m loopx.benchmark_adapters.skillsbench_runner_profile capture
  SKILLSBENCH_LOCAL_CODEX_PROXY_HOST   Local proxy host, default 127.0.0.1
  SKILLSBENCH_LOCAL_CODEX_PROXY_PORT   Local proxy port, default 18180
  SKILLSBENCH_DOCKER_PROXY_HOST        Remote Docker bridge host for benchmark
                                       setup/verifier egress; default auto
  SKILLSBENCH_BENCHMARK_EGRESS_PROXY_MODE
                                       Benchmark setup/verifier egress mode:
                                       require (default), auto, or off
  SKILLSBENCH_DOCKER_API_VERSION       Remote Docker daemon API version passed
                                       to Docker CLI/Compose; default auto
  SKILLSBENCH_ROUTE                    Route, default codex-cli-goal-baseline
  SKILLSBENCH_MODEL                    Model, default gpt-5.5
  SKILLSBENCH_REASONING_EFFORT         Reasoning effort, default xhigh
  SKILLSBENCH_REMOTE_CODEX_BIN          Codex CLI executable on remote runner;
                                       default codex from remote PATH
  SKILLSBENCH_LOCAL_CODEX_SANDBOX      Host Codex sandbox mode; default
                                       workspace-write
  SKILLSBENCH_CLI_GOAL_THREAD_PREWARM  Set to 1 to prewarm the persisted Codex
                                       TUI thread before submitting /goal
  SKILLSBENCH_ALLOW_STAGED_BOOTSTRAP_REPAIR_RUN
                                       Set to 1 to let the runner stage an
                                       isolated task copy and apply its
                                       public-safe setup bootstrap repairs
  SKILLSBENCH_SETUP_ONLY_PUBLIC_PREFLIGHT
                                       Set to 1 to stop after real job-root and
                                       environment materialization, before any
                                       agent or verifier lifecycle
  SKILLSBENCH_PRODUCT_MODE_SOFT_VERIFY_POLICY
                                       Optional product-mode intermediate
                                       verifier policy: every-round or
                                       final-only; unset preserves runner default
  SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_COMMAND
                                       Private task-free bridge probe command
  SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_SOLVER_COMMAND
                                       Private scored-workspace bridge command
  SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND
                                       Optional private agent bridge command;
                                       defaults to the relay-generated wrapper
  SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND_INSTRUMENTED
                                       Set to 1 only when the explicit agent
                                       command emits the public-safe operation
                                       trace contract; default 0
  SKILLSBENCH_LOOPX_TURN_VALIDATION_COMMAND
                                       Independent scored-workspace validator
                                       required by loopx-turn-agent-cli
  SKILLSBENCH_LOOPX_TURN_MAX_TURNS      Maximum validated Turns, default 1
  SKILLSBENCH_LOOPX_TURN_PROGRESS_EXIT_CODE
                                       Validator code for intermediate progress,
                                       default 10; 0 remains terminal completion
  SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICY
                                       validator (default), fixed-n, or stability
  SKILLSBENCH_BUILD_STALL_TIMEOUT_SEC  Setup stall timeout, default 3600;
                                       0 disables cap
  SKILLSBENCH_RUN_TIMEOUT_SEC          Supervisor timeout, default 28800
  SKILLSBENCH_PUBLIC_ARTIFACT_SYNC_INTERVAL_SEC
                                       Incremental public artifact sync interval;
                                       defaults to 30 for setup-only and 0 otherwise
  SKILLSBENCH_TUNNEL_PROBE_TIMEOUT_SEC Reverse-tunnel CONNECT probe timeout,
                                       default 20
  SKILLSBENCH_TUNNEL_READY_TIMEOUT_SEC Reverse-tunnel readiness budget,
                                       default 60
  SKILLSBENCH_TUNNEL_HEALTH_INTERVAL_SEC Ongoing CONNECT probe interval,
                                       default 30; 0 disables
  SKILLSBENCH_TUNNEL_HEALTH_FAILURE_THRESHOLD Consecutive failures before
                                       reconnect, default 2
  SKILLSBENCH_TUNNEL_RECONNECT_ATTEMPTS Bounded reconnect attempts, default 2
  SKILLSBENCH_PARALLEL_CASES           Batch concurrency, default 3
  SKILLSBENCH_BATCH_CASE_START_GAP_SEC Delay between case starts, default 3
  SKILLSBENCH_GOAL_ID                  Local evidence goal id, default loopx-meta
  SKILLSBENCH_RUN_STAMP                Deterministic timestamp override
  SKILLSBENCH_SSH_OPTIONS              Extra ssh options, one shell word each
  SKILLSBENCH_APPEND_HISTORY           Set to 1 to append LoopX history
  SKILLSBENCH_REGISTRY                 Optional registry path for history append
  SKILLSBENCH_SKIP_GLOBAL_LEDGER_SYNC  Set to 1 to keep the remote run out of
                                       the global benchmark ledger
  SKILLSBENCH_SKIP_CURRENT_AGGREGATE_UPDATE
                                       Set to 1 to skip the remote current
                                       aggregate update
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

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runner_profile="${SKILLSBENCH_RUNNER_PROFILE:-}"
runner_profile_loaded=false
runner_profile_args=(export-shell)
unset SKILLSBENCH_RUNNER_PROFILE_DISCOVERED
if [[ -n "$runner_profile" ]]; then
  runner_profile_args+=(--profile "$runner_profile")
else
  runner_profile_args+=(--if-present)
fi
if ! runner_profile_exports="$(
  PYTHONPATH="${repo_root}${PYTHONPATH:+:${PYTHONPATH}}" \
    python3 -m loopx.benchmark_adapters.skillsbench_runner_profile \
    "${runner_profile_args[@]}"
)"; then
  exit 2
fi
if [[ -n "$runner_profile_exports" ]]; then
  # The helper emits only whitelisted variable names with shlex-quoted values.
  eval "$runner_profile_exports"
fi
if [[ "${SKILLSBENCH_RUNNER_PROFILE_DISCOVERED:-}" == "1" ]]; then
  runner_profile_loaded=true
fi
unset runner_profile_exports SKILLSBENCH_RUNNER_PROFILE_DISCOVERED

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
codex_cli_goal_thread_prewarm="${SKILLSBENCH_CLI_GOAL_THREAD_PREWARM:-0}"
if [[ "$codex_cli_goal_thread_prewarm" != "0" && "$codex_cli_goal_thread_prewarm" != "1" ]]; then
  echo "SKILLSBENCH_CLI_GOAL_THREAD_PREWARM must be 0 or 1" >&2
  exit 2
fi
skip_global_ledger_sync="${SKILLSBENCH_SKIP_GLOBAL_LEDGER_SYNC:-0}"
skip_current_aggregate_update="${SKILLSBENCH_SKIP_CURRENT_AGGREGATE_UPDATE:-0}"
allow_staged_bootstrap_repair_run="${SKILLSBENCH_ALLOW_STAGED_BOOTSTRAP_REPAIR_RUN:-0}"
setup_only_public_preflight="${SKILLSBENCH_SETUP_ONLY_PUBLIC_PREFLIGHT:-0}"
benchmark_egress_proxy_mode="${SKILLSBENCH_BENCHMARK_EGRESS_PROXY_MODE:-require}"
product_mode_soft_verify_policy="${SKILLSBENCH_PRODUCT_MODE_SOFT_VERIFY_POLICY:-}"
remote_command_file_bridge_probe_command="${SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_COMMAND:-}"
remote_command_file_bridge_solver_command="${SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_SOLVER_COMMAND:-}"
remote_command_file_bridge_agent_command="${SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND:-}"
remote_command_file_bridge_agent_command_instrumented="${SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND_INSTRUMENTED:-0}"
loopx_turn_validation_command="${SKILLSBENCH_LOOPX_TURN_VALIDATION_COMMAND:-}"
loopx_turn_max_turns="${SKILLSBENCH_LOOPX_TURN_MAX_TURNS:-1}"
loopx_turn_progress_exit_code="${SKILLSBENCH_LOOPX_TURN_PROGRESS_EXIT_CODE:-10}"
loopx_turn_terminal_policy="${SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICY:-validator}"
validate_bool_toggle() {
  local env_name="$1"
  local value="$2"
  if [[ "$value" != "0" && "$value" != "1" ]]; then
    echo "${env_name} must be 0 or 1" >&2
    exit 2
  fi
}
validate_bool_toggle SKILLSBENCH_SKIP_GLOBAL_LEDGER_SYNC "$skip_global_ledger_sync"
validate_bool_toggle \
  SKILLSBENCH_SKIP_CURRENT_AGGREGATE_UPDATE "$skip_current_aggregate_update"
validate_bool_toggle \
  SKILLSBENCH_ALLOW_STAGED_BOOTSTRAP_REPAIR_RUN "$allow_staged_bootstrap_repair_run"
validate_bool_toggle \
  SKILLSBENCH_SETUP_ONLY_PUBLIC_PREFLIGHT "$setup_only_public_preflight"
if [[ "$benchmark_egress_proxy_mode" != "require" ]] &&
  [[ "$benchmark_egress_proxy_mode" != "auto" ]] &&
  [[ "$benchmark_egress_proxy_mode" != "off" ]]; then
  echo "SKILLSBENCH_BENCHMARK_EGRESS_PROXY_MODE must be require, auto, or off" >&2
  exit 2
fi
validate_bool_toggle \
  SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND_INSTRUMENTED \
  "$remote_command_file_bridge_agent_command_instrumented"
if [[ "$remote_command_file_bridge_agent_command_instrumented" == "1" ]] &&
  [[ -z "$remote_command_file_bridge_agent_command" ]]; then
  echo "SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND_INSTRUMENTED requires SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_AGENT_COMMAND" >&2
  exit 2
fi
if [[ -n "$product_mode_soft_verify_policy" ]] &&
  [[ "$product_mode_soft_verify_policy" != "every-round" ]] &&
  [[ "$product_mode_soft_verify_policy" != "final-only" ]]; then
  echo "SKILLSBENCH_PRODUCT_MODE_SOFT_VERIFY_POLICY must be every-round or final-only" >&2
  exit 2
fi
remote_codex_bin_mode="path_lookup"
if [[ -n "${SKILLSBENCH_REMOTE_CODEX_BIN:-}" ]]; then
  remote_codex_bin_mode="explicit"
fi
if [[ "$dry_run" == "false" && "$setup_only_public_preflight" != "1" ]]; then
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
if [[ "$route" == "loopx-turn-agent-cli" ]] &&
  [[ -z "$loopx_turn_validation_command" ]]; then
  echo "SKILLSBENCH_LOOPX_TURN_VALIDATION_COMMAND is required for loopx-turn-agent-cli" >&2
  exit 2
fi
if [[ "$route" == "loopx-turn-agent-cli" ]]; then
  if [[ ! "$loopx_turn_max_turns" =~ ^[1-9][0-9]*$ ]]; then
    echo "SKILLSBENCH_LOOPX_TURN_MAX_TURNS must be a positive integer" >&2
    exit 2
  fi
  if [[ ! "$loopx_turn_progress_exit_code" =~ ^[1-9][0-9]*$ ]] ||
    ((10#$loopx_turn_progress_exit_code > 255)); then
    echo "SKILLSBENCH_LOOPX_TURN_PROGRESS_EXIT_CODE must be between 1 and 255" >&2
    exit 2
  fi
  if [[ "$loopx_turn_terminal_policy" != "validator" ]] &&
    [[ "$loopx_turn_terminal_policy" != "fixed-n" ]] &&
    [[ "$loopx_turn_terminal_policy" != "stability" ]]; then
    echo "SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICY must be validator, fixed-n, or stability" >&2
    exit 2
  fi
fi
model="${SKILLSBENCH_MODEL:-gpt-5.5}"
reasoning_effort="${SKILLSBENCH_REASONING_EFFORT:-xhigh}"
build_stall_timeout="${SKILLSBENCH_BUILD_STALL_TIMEOUT_SEC:-3600}"
run_timeout="${SKILLSBENCH_RUN_TIMEOUT_SEC:-28800}"
if [[ -n "${SKILLSBENCH_PUBLIC_ARTIFACT_SYNC_INTERVAL_SEC:-}" ]]; then
  public_artifact_sync_interval="$SKILLSBENCH_PUBLIC_ARTIFACT_SYNC_INTERVAL_SEC"
elif [[ "$setup_only_public_preflight" == "1" ]]; then
  public_artifact_sync_interval=30
else
  public_artifact_sync_interval=0
fi
tunnel_probe_timeout="${SKILLSBENCH_TUNNEL_PROBE_TIMEOUT_SEC:-20}"
tunnel_ready_timeout="${SKILLSBENCH_TUNNEL_READY_TIMEOUT_SEC:-60}"
tunnel_health_interval="${SKILLSBENCH_TUNNEL_HEALTH_INTERVAL_SEC:-30}"
tunnel_health_failure_threshold="${SKILLSBENCH_TUNNEL_HEALTH_FAILURE_THRESHOLD:-2}"
tunnel_reconnect_attempts="${SKILLSBENCH_TUNNEL_RECONNECT_ATTEMPTS:-2}"
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
if [[ "$codex_cli_goal_thread_prewarm" == "1" ]]; then
  extra_runner_args+=(--codex-cli-goal-thread-prewarm)
fi
if [[ "$allow_staged_bootstrap_repair_run" == "1" ]]; then
  extra_runner_args+=(--allow-staged-bootstrap-repair-run)
fi
if [[ "$setup_only_public_preflight" == "1" ]]; then
  extra_runner_args+=(--setup-only-public-preflight)
fi
if [[ -n "$product_mode_soft_verify_policy" ]]; then
  extra_runner_args+=(
    --product-mode-soft-verify-policy "$product_mode_soft_verify_policy"
  )
fi
if [[ -n "$remote_command_file_bridge_probe_command" ]]; then
  extra_runner_args+=(
    --remote-command-file-bridge-probe-command
    "$remote_command_file_bridge_probe_command"
  )
fi
if [[ -n "$remote_command_file_bridge_solver_command" ]]; then
  extra_runner_args+=(
    --remote-command-file-bridge-solver-command
    "$remote_command_file_bridge_solver_command"
  )
fi
if [[ -n "$remote_command_file_bridge_agent_command" ]]; then
  extra_runner_args+=(
    --remote-command-file-bridge-agent-command
    "$remote_command_file_bridge_agent_command"
  )
fi
if [[ "$remote_command_file_bridge_agent_command_instrumented" == "1" ]]; then
  extra_runner_args+=(--remote-command-file-bridge-agent-command-instrumented)
fi
if [[ -n "$loopx_turn_validation_command" ]]; then
  extra_runner_args+=(
    --loopx-turn-validation-command
    "$loopx_turn_validation_command"
  )
fi
if [[ "$route" == "loopx-turn-agent-cli" ]]; then
  extra_runner_args+=(
    --loopx-turn-max-turns
    "$loopx_turn_max_turns"
    --loopx-turn-progress-exit-code
    "$loopx_turn_progress_exit_code"
    --loopx-turn-terminal-policy
    "$loopx_turn_terminal_policy"
  )
fi
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
if [[ "$skip_global_ledger_sync" == "1" ]]; then
  extra_runner_args+=(--skip-global-ledger-sync)
fi
if [[ "$skip_current_aggregate_update" == "1" ]]; then
  extra_runner_args+=(--skip-current-aggregate-update)
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
    --benchmark-egress-proxy-mode "$benchmark_egress_proxy_mode" \
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
  --tunnel-health-interval-sec "$tunnel_health_interval"
  --tunnel-health-failure-threshold "$tunnel_health_failure_threshold"
  --tunnel-reconnect-attempts "$tunnel_reconnect_attempts"
  --tunnel-reconnect-ready-timeout-sec "$tunnel_ready_timeout"
  --run-timeout-sec "$run_timeout"
  --public-artifact-sync-interval-sec "$public_artifact_sync_interval"
  --remote-failure-cleanup-pattern "$job_name"
  --remote-failure-cleanup-include-docker
  --remote-command "$remote_command"
  --remote-public-artifact-root "${SKILLSBENCH_REMOTE_ROOT}/.local/private-benchmark-jobs"
  --remote-public-artifact-glob "${job_name}*/runner_prerequisites.public.json"
  --remote-public-artifact-glob "${job_name}*/setup_only_preflight.public.json"
  --remote-public-artifact-glob "${job_name}*/loopx_controller_trace.public.json"
  --remote-public-artifact-glob "${job_name}*/runner_config.public.json"
  --remote-public-artifact-glob "${job_name}*/*/benchmark_run.compact.json"
  --remote-public-artifact-glob "${job_name}*/host_local_acp_relay_traces/*.compact.json"
  --local-public-artifact-dir "$public_dir"
  --private-log-path "${private_dir}/remote-command.log"
  --public-output-path "${public_dir}/supervisor.public.json"
)

if [[ "$setup_only_public_preflight" != "1" ]]; then
  supervisor_cmd+=(
    --local-run-ledger-path "$local_run_ledger"
    --local-run-group-id "$run_group"
    --local-ledger-catchup-root "$public_root"
    --local-ledger-catchup-run-group-contains "$ledger_catchup_group"
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
  printf 'docker_proxy_host_recorded=false\n'
  printf 'docker_proxy_endpoint_mode=%s\n' "$docker_proxy_endpoint_mode"
  printf 'docker_api_version=%s\n' "$docker_api_version"
  printf 'remote_codex_bin_mode=%s\n' "$remote_codex_bin_mode"
  printf 'runner_profile_loaded=%s\n' "$runner_profile_loaded"
  printf 'runner_profile_path_recorded=false\n'
  printf 'runner_profile_values_recorded=false\n'
  printf 'local_codex_sandbox=%s\n' "$local_codex_sandbox"
  printf 'codex_cli_goal_thread_prewarm=%s\n' "$codex_cli_goal_thread_prewarm"
  printf 'allow_staged_bootstrap_repair_run=%s\n' "$allow_staged_bootstrap_repair_run"
  printf 'setup_only_public_preflight=%s\n' "$setup_only_public_preflight"
  printf 'public_artifact_sync_interval_sec=%s\n' \
    "$public_artifact_sync_interval"
  printf 'benchmark_egress_proxy_mode=%s\n' "$benchmark_egress_proxy_mode"
  printf 'product_mode_soft_verify_policy=%s\n' \
    "${product_mode_soft_verify_policy:-runner-default}"
  printf 'remote_command_file_bridge_probe_command_configured=%s\n' \
    "$([[ -n "$remote_command_file_bridge_probe_command" ]] && echo 1 || echo 0)"
  printf 'remote_command_file_bridge_solver_command_configured=%s\n' \
    "$([[ -n "$remote_command_file_bridge_solver_command" ]] && echo 1 || echo 0)"
  printf 'remote_command_file_bridge_agent_command_configured=%s\n' \
    "$([[ -n "$remote_command_file_bridge_agent_command" ]] && echo 1 || echo 0)"
  printf 'remote_command_file_bridge_agent_command_instrumented=%s\n' \
    "$remote_command_file_bridge_agent_command_instrumented"
  printf 'loopx_turn_validation_command_configured=%s\n' \
    "$([[ -n "$loopx_turn_validation_command" ]] && echo 1 || echo 0)"
  printf 'loopx_turn_max_turns=%s\n' "$loopx_turn_max_turns"
  printf 'loopx_turn_progress_exit_code=%s\n' "$loopx_turn_progress_exit_code"
  printf 'loopx_turn_terminal_policy=%s\n' "$loopx_turn_terminal_policy"
  printf 'skip_global_ledger_sync=%s\n' "$skip_global_ledger_sync"
  printf 'skip_current_aggregate_update=%s\n' "$skip_current_aggregate_update"
  printf 'local_run_ledger=%s\n' "$local_run_ledger"
  if [[ -n "${standard_aggregate:-}" ]]; then
    printf 'standard_aggregate=%s\n' "$standard_aggregate"
  fi
  if [[ "$runner_profile_loaded" == "true" ]] ||
    [[ -n "$remote_command_file_bridge_probe_command" ]] ||
    [[ -n "$remote_command_file_bridge_solver_command" ]] ||
    [[ -n "$remote_command_file_bridge_agent_command" ]] ||
    [[ -n "$loopx_turn_validation_command" ]]; then
    printf 'private_runner_command_values_redacted=true\n'
    printf 'private_runner_arg_names='
    [[ -n "$remote_command_file_bridge_probe_command" ]] &&
      printf '%s ' --remote-command-file-bridge-probe-command
    [[ -n "$remote_command_file_bridge_solver_command" ]] &&
      printf '%s ' --remote-command-file-bridge-solver-command
    [[ -n "$remote_command_file_bridge_agent_command" ]] &&
      printf '%s ' --remote-command-file-bridge-agent-command
    [[ "$remote_command_file_bridge_agent_command_instrumented" == "1" ]] &&
      printf '%s ' --remote-command-file-bridge-agent-command-instrumented
    [[ -n "$loopx_turn_validation_command" ]] &&
      printf '%s ' --loopx-turn-validation-command
    [[ "$route" == "loopx-turn-agent-cli" ]] &&
      printf '%s ' --loopx-turn-max-turns --loopx-turn-progress-exit-code
    [[ "$route" == "loopx-turn-agent-cli" ]] &&
      printf '%s ' --loopx-turn-terminal-policy
    printf '\n'
    printf 'remote_command=<redacted-private-runner-command-values>\n'
    printf 'supervisor_command=<redacted-private-runner-command-values>\n'
  else
    printf 'private_runner_command_values_redacted=false\n'
    printf 'remote_command=%s\n' "$remote_command"
    printf 'supervisor_command='
    printf '%q ' "${supervisor_cmd[@]}"
    printf '\n'
  fi
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
codex_cli_goal_thread_prewarm=${codex_cli_goal_thread_prewarm}
allow_staged_bootstrap_repair_run=${allow_staged_bootstrap_repair_run}
setup_only_public_preflight=${setup_only_public_preflight}
public_artifact_sync_interval_sec=${public_artifact_sync_interval}
EOF
