#!/usr/bin/env python3
"""Print a compact summary for one Harbor job."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def extract_reward(payload: dict) -> int | float | None:
    reward = payload.get("reward")
    if isinstance(reward, dict):
        reward = reward.get("reward") or reward.get("score")
    if isinstance(reward, (int, float)):
        return reward

    verifier_result = payload.get("verifier_result")
    if not isinstance(verifier_result, dict):
        return None
    rewards = verifier_result.get("rewards")
    if not isinstance(rewards, dict):
        return None
    reward = rewards.get("reward")
    return reward if isinstance(reward, (int, float)) else None


def main() -> int:
    job = Path(sys.argv[1])
    trials = sorted(path for path in job.glob("**/result.json") if path.parent != job)
    rows = []
    for path in trials:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        reward = extract_reward(payload)
        rows.append((path.parent.name, reward, payload.get("exception_info")))
    numeric = [float(row[1]) for row in rows if isinstance(row[1], (int, float))]
    print(json.dumps({
        "job": str(job),
        "trials_found": len(rows),
        "rewards_found": len(numeric),
        "mean_reward": sum(numeric) / len(numeric) if numeric else None,
        "rows": rows,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
