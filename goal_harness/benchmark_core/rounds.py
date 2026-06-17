from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
