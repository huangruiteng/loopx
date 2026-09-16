#!/usr/bin/env bash
# Fair rerun of the three LoopX treatments after host/delivery fixes.
set -euo pipefail
trap 'exit 130' INT TERM

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-all}"
shift $(( $# > 0 ? 1 : 0 ))

case "$MODE" in
  all|ssh-goal|codex-cli|heartbeat) ;;
  *) echo "usage: $0 [all|ssh-goal|codex-cli|heartbeat] [task ...]" >&2; exit 2 ;;
esac

MODEL="${MR_MODEL:-openai/gpt-5.6-sol}"
EFFORT="${MR_EFFORT:-xhigh}"
CONCURRENT="${MR_CONCURRENT:-2}"
GOAL_TIMEOUT="${MR_GOAL_TIMEOUT_SEC:-14400}"
HEARTBEAT_SEGMENT_TIMEOUT="${MR_HEARTBEAT_SEGMENT_TIMEOUT_SEC:-7200}"
TURN_IDLE_TIMEOUT="${MR_LOOPX_TURN_IDLE_TIMEOUT_SEC:-7200}"
AGENT_TIMEOUT_MULTIPLIER="${MR_AGENT_TIMEOUT_MULTIPLIER:-3.0}"
PORT_BASE="${MR_GATEWAY_BASE_PORT:-4411}"
OUT_ROOT="${MR_LOOPX_RERUN_ROOT:-$DIR/jobs/loopx-three-arms-54-fair-rerun-20260908}"
LOG_ROOT="${MR_LOOPX_RERUN_LOG_ROOT:-$DIR/logs/loopx-three-arms-54-fair-rerun-20260908}"
LOOPX_ROOT="${MR_LOOPX_ROOT:-$DIR/../loopx-official-latest}"
LOOPX_REVISION="$(git -C "$LOOPX_ROOT" rev-parse --verify HEAD)"
LOOPX_REVISION_SHORT="${LOOPX_REVISION:0:12}"

mapfile -t ALL_TASKS < <(
  cd "$DIR"
  python3 - <<'PY'
from goal30_subset import SUBSET
from hard24_subset import HARD_SUBSET
from remaining4_subset import REMAINING_SUBSET

tasks = list(dict.fromkeys([*SUBSET, *HARD_SUBSET, *REMAINING_SUBSET]))
if len(tasks) != 54:
    raise SystemExit(f"expected 54 tasks, got {len(tasks)}")
print("\n".join(tasks))
PY
)

if (( $# )); then
  TASKS=("$@")
  for requested in "${TASKS[@]}"; do
    found=0
    for allowed in "${ALL_TASKS[@]}"; do
      [[ "$requested" == "$allowed" ]] && found=1 && break
    done
    (( found == 1 )) || { echo "task is outside the frozen 54: $requested" >&2; exit 2; }
  done
else
  TASKS=("${ALL_TASKS[@]}")
fi

port_for() {
  case "$1" in
    ssh-goal) echo "$PORT_BASE" ;;
    codex-cli) echo "$((PORT_BASE + 1))" ;;
    heartbeat) echo "$((PORT_BASE + 2))" ;;
  esac
}

arm_for() {
  case "$1" in
    ssh-goal) echo loopx-native ;;
    codex-cli) echo loopx-native-codex-cli ;;
    heartbeat) echo loopx-native-heartbeat ;;
  esac
}

preflight_arm() {
  local arm_mode="$1"
  local port jobs
  port="$(port_for "$arm_mode")"
  jobs="$OUT_ROOT/$arm_mode"
  [[ "$port" != 4141 && "$port" != 4250 ]] || {
    echo "prohibited DeepSWE gateway port: $port" >&2
    return 2
  }
  if ss -ltnH "sport = :$port" | grep -q .; then
    echo "gateway port already occupied: $port" >&2
    return 1
  fi
  if pgrep -af "[p]ier_cn.py.*--jobs-dir $jobs" >/dev/null; then
    echo "$arm_mode already running: $jobs" >&2
    return 1
  fi

  mkdir -p "$jobs" "$LOG_ROOT"
  "$DIR/.venv-user-395647/bin/python" "$DIR/preflight_loopx_rerun.py" \
    --arm "$arm_mode" --loopx-root "$LOOPX_ROOT" --port "$port" \
    --model "$MODEL" --effort "$EFFORT" --goal-timeout "$GOAL_TIMEOUT" \
    --heartbeat-segment-timeout "$HEARTBEAT_SEGMENT_TIMEOUT" \
    --turn-idle-timeout "$TURN_IDLE_TIMEOUT" \
    --agent-timeout-multiplier "$AGENT_TIMEOUT_MULTIPLIER" \
    --output "$LOG_ROOT/admission-$arm_mode.json"
}

run_arm() {
  local arm_mode="$1"
  local port arm jobs label
  port="$(port_for "$arm_mode")"
  arm="$(arm_for "$arm_mode")"
  jobs="$OUT_ROOT/$arm_mode"
  label="loopx-fair54-20260908-$arm_mode"
  local -a include=()
  local task
  for task in "${TASKS[@]}"; do include+=(-i "$task"); done
  echo "$(date -Is) start $arm_mode tasks=${#TASKS[@]} concurrency=$CONCURRENT port=$port"
  (
    cd "$DIR"
    PIER_CUSTOM_NETWORKS=1 \
    MR_MODELONLY_NET=1 MR_MODELONLY_HOST=127.0.0.1 MR_MODELONLY_PORT="$port" \
    MR_API_BASE="http://127.0.0.1:$port/v1" \
    MR_AGENT=codex MR_MODEL="$MODEL" MR_EFFORT="$EFFORT" MR_REASONING_EFFORT="$EFFORT" \
    MR_CODEX_ARM="$arm" MR_LOOPX_MODE="$arm_mode" MR_LOOPX_ROOT="$LOOPX_ROOT" \
    MR_LOOPX_PROFILE_ROOT="/tmp/loopx-profile-fair54-$LOOPX_REVISION_SHORT-$arm_mode" \
    MR_LOOPX_PREFLIGHT=0 MR_LOOPX_WEN_COMPAT=1 \
    MR_GOAL_TIMEOUT_SEC="$GOAL_TIMEOUT" MR_UPSTREAM_TIMEOUT="$GOAL_TIMEOUT" \
    MR_HEARTBEAT_SEGMENT_TIMEOUT_SEC="$HEARTBEAT_SEGMENT_TIMEOUT" \
    MR_LOOPX_TURN_IDLE_TIMEOUT_SEC="$TURN_IDLE_TIMEOUT" \
    MR_RUN_LABEL="$label" MR_GATEWAY_PORT="$port" MR_JOBS_DIR="$jobs" \
    MR_LOG_PATH="$LOG_ROOT/gateway_calls_$arm_mode.jsonl" \
    MR_GATEWAY_OUT="$LOG_ROOT/gateway_$arm_mode.out" \
    MR_GATEWAY_MAX_RETRIES=12 MR_GATEWAY_RETRY_BASE_SEC=5 MR_GATEWAY_RETRY_CAP_SEC=60 \
      ./run.sh --all "${include[@]}" -k 1 -n "$CONCURRENT" \
        --agent-timeout-multiplier "$AGENT_TIMEOUT_MULTIPLIER"
  ) >"$LOG_ROOT/$arm_mode.log" 2>&1
  echo "$(date -Is) finish $arm_mode"
}

if [[ "$MODE" == all ]]; then
  for arm_mode in ssh-goal codex-cli heartbeat; do
    preflight_arm "$arm_mode"
  done
  "$DIR/.venv-user-395647/bin/python" - "$LOG_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
receipts = [json.loads((root / f"admission-{arm}.json").read_text()) for arm in ("ssh-goal", "codex-cli", "heartbeat")]
fixed = (
    "model",
    "effort",
    "agent_timeout_multiplier",
    "goal_timeout_seconds",
    "heartbeat_segment_timeout_seconds",
    "turn_idle_timeout_seconds",
    "task_count",
    "task_manifest_sha256",
    "loopx_revision",
    "network_policy",
    "sandbox_policy",
    "web_search",
    "task_correctness_authority",
)
for key in fixed:
    values = {json.dumps(receipt.get(key), sort_keys=True) for receipt in receipts}
    if len(values) != 1:
        raise SystemExit(f"cross-arm admission mismatch for {key}: {values}")
surfaces = {receipt["host_surface"] for receipt in receipts}
if len(surfaces) != 3:
    raise SystemExit(f"host surfaces are not distinct: {surfaces}")
if not all(receipt.get("admitted") for receipt in receipts):
    raise SystemExit("at least one arm was not admitted")
print("cross-arm admission: matched controls, three distinct execution surfaces")
PY
  for arm_mode in ssh-goal codex-cli heartbeat; do
    run_arm "$arm_mode"
  done
  exit 0
fi

preflight_arm "$MODE"
run_arm "$MODE"
