from __future__ import annotations

from dataclasses import dataclass
from typing import Any


BENCHMARK_ROUND_ARTIFACT_RESTORE_PLAN_SCHEMA_VERSION = (
    "benchmark_round_artifact_restore_plan_v0"
)
_UNSAFE_SNAPSHOT_REF_MARKERS = (
    "/Users/",
    "/private/",
    "/tmp/",
    "\\",
    "trajectory",
    "task.md",
    "instruction.md",
    "verifier",
    "logs/",
    "raw/",
    "credential",
    "secret",
)


@dataclass(frozen=True)
class RoundReward:
    agent_round: int
    reward: float | None = None
    passed: bool | None = None
    reward_present: bool = True


def compact_round_rewards(records: list[Any]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        agent_round = record.get("agent_round")
        if not isinstance(agent_round, int) or isinstance(agent_round, bool):
            continue
        if agent_round <= 0:
            continue
        item: dict[str, Any] = {"agent_round": agent_round}
        reward = record.get("reward")
        if isinstance(reward, (int, float)) and not isinstance(reward, bool):
            item["reward"] = float(reward)
            item["reward_present"] = True
        elif record.get("reward_present") is False:
            item["reward_present"] = False
        if isinstance(record.get("passed"), bool):
            item["passed"] = record["passed"]
        elif "reward" in item:
            item["passed"] = item["reward"] >= 1
        compact.append(item)
    return sorted(compact, key=lambda item: item["agent_round"])


def _public_snapshot_ref(value: Any) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    ref = str(value).strip()
    if not ref or ref in {".", ".."}:
        return ""
    lower_ref = ref.lower()
    if any(marker.lower() in lower_ref for marker in _UNSAFE_SNAPSHOT_REF_MARKERS):
        return ""
    return ref[:200]


def compact_round_artifact_snapshots(records: list[Any]) -> list[dict[str, Any]]:
    """Return public-safe per-round artifact snapshot handles.

    Snapshot handles must be logical compact references, not raw local paths.
    Host adapters own the actual filesystem copy/restore implementation.
    """

    compact: list[dict[str, Any]] = []
    seen_rounds: set[int] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        agent_round = record.get("agent_round")
        if not isinstance(agent_round, int) or isinstance(agent_round, bool):
            continue
        if agent_round <= 0 or agent_round in seen_rounds:
            continue
        snapshot_ref = (
            _public_snapshot_ref(record.get("snapshot_ref"))
            or _public_snapshot_ref(record.get("artifact_ref"))
            or _public_snapshot_ref(record.get("restore_handle"))
        )
        if not snapshot_ref:
            continue
        item: dict[str, Any] = {
            "agent_round": agent_round,
            "snapshot_ref": snapshot_ref,
            "restore_kind": "benchmark_host_round_snapshot",
        }
        if isinstance(record.get("ready_for_restore"), bool):
            item["ready_for_restore"] = record["ready_for_restore"]
        else:
            item["ready_for_restore"] = True
        compact.append(item)
        seen_rounds.add(agent_round)
    return sorted(compact, key=lambda item: item["agent_round"])


def summarize_round_rewards(records: list[Any]) -> dict[str, Any]:
    compact = compact_round_rewards(records)
    numeric = [item for item in compact if isinstance(item.get("reward"), float)]
    first_success_round = None
    for item in compact:
        if item.get("passed") is True:
            first_success_round = item["agent_round"]
            break
    if not numeric:
        return {
            "round_rewards": compact,
            "round_reward_count": len(compact),
            "first_success_round": first_success_round,
        }
    final = numeric[-1]
    best = max(numeric, key=lambda item: (item["reward"], -item["agent_round"]))
    return {
        "round_rewards": compact,
        "round_reward_count": len(compact),
        "first_success_round": first_success_round,
        "final_round": final["agent_round"],
        "final_round_reward": final["reward"],
        "final_round_passed": final.get("passed"),
        "best_reward_round": best["agent_round"],
        "best_round_reward": best["reward"],
        "best_round_passed": best.get("passed"),
        "best_round_is_final": best["agent_round"] == final["agent_round"],
    }


def build_round_artifact_restore_plan(
    *,
    round_rewards: list[Any],
    round_artifact_snapshots: list[Any],
) -> dict[str, Any]:
    """Build the public control-plane plan for best-round artifact selection.

    This makes best-round scoring executable only when the best scored round is
    already final or has a compact per-round snapshot handle that a host adapter
    can restore. It deliberately records no raw paths or commands.
    """

    reward_summary = summarize_round_rewards(round_rewards)
    snapshots = compact_round_artifact_snapshots(round_artifact_snapshots)
    snapshots_by_round = {item["agent_round"]: item for item in snapshots}
    best_round = reward_summary.get("best_reward_round")
    final_round = reward_summary.get("final_round")
    best_round_is_final = reward_summary.get("best_round_is_final") is True

    selected_snapshot = (
        snapshots_by_round.get(best_round)
        if isinstance(best_round, int) and not isinstance(best_round, bool)
        else None
    )
    restore_required = bool(best_round is not None and not best_round_is_final)
    if best_round is None:
        executable = False
        blocked_reason = "missing_numeric_round_reward"
        action = "record_round_rewards_before_final_selection"
    elif best_round_is_final:
        executable = True
        blocked_reason = ""
        action = "keep_final_workspace"
    elif selected_snapshot and selected_snapshot.get("ready_for_restore") is not False:
        executable = True
        blocked_reason = ""
        action = "restore_best_round_snapshot_before_final_scoring"
    elif selected_snapshot:
        executable = False
        blocked_reason = "best_round_snapshot_not_ready_for_restore"
        action = "repair_best_round_snapshot_before_final_selection"
    else:
        executable = False
        blocked_reason = "missing_snapshot_for_best_round"
        action = "capture_per_round_snapshot_before_using_best_score_policy"

    restore_plan: dict[str, Any] = {"action": action}
    if selected_snapshot and restore_required:
        restore_plan["snapshot_ref"] = selected_snapshot["snapshot_ref"]
        restore_plan["agent_round"] = selected_snapshot["agent_round"]

    return {
        "schema_version": BENCHMARK_ROUND_ARTIFACT_RESTORE_PLAN_SCHEMA_VERSION,
        "policy_id": "best_round_artifact_restore_v0",
        "final_selection_policy": "use_best_scored_round_when_executable_snapshot_available",
        "selected_round": best_round,
        "selected_reward": reward_summary.get("best_round_reward"),
        "selected_passed": reward_summary.get("best_round_passed"),
        "final_round": final_round,
        "final_round_reward": reward_summary.get("final_round_reward"),
        "best_round_is_final": best_round_is_final,
        "restore_required": restore_required,
        "executable_final_selection": executable,
        "blocked_reason": blocked_reason,
        "round_snapshot_count": len(snapshots),
        "rounds_with_snapshot": [item["agent_round"] for item in snapshots],
        "restore_plan": restore_plan,
        "round_reward_summary": reward_summary,
        "boundary": {
            "raw_snapshot_paths_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_verifier_output_read": False,
            "trajectory_read": False,
            "host_restore_command_recorded": False,
        },
    }
