from __future__ import annotations

import json
from pathlib import Path
from typing import Any


GOAL_ID = "loopx-auto-research-demo"
METRIC_NAME = "demo_quality_score"
BASELINE = 1.0
HYPOTHESIS_ID = "hyp_state_a2a_round"
TODO_ID = "todo_auto_research_demo_001"
AGENT_ID = "research-executor"
MECHANISM_FAMILY = "state_a2a_iteration"
HYPOTHESIS_TEXT = "Use a small state-mediated handoff loop to improve the shared candidate."
GROUNDING_REF = "kernel:state_a2a_metric_demo"


def research_contract(*, goal_id: str = GOAL_ID) -> dict[str, Any]:
    return {
        "schema_version": "research_contract_v0",
        "goal_id": goal_id,
        "research_objective": "Validate compact multi-agent research evidence.",
        "editable_scope": ["candidate_strategy", "hypothesis_text", "todo_handoff"],
        "protected_scope": ["metric_definition", "baseline_metric", "holdout_split"],
        "metric": {
            "name": METRIC_NAME,
            "direction": "maximize",
            "baseline": BASELINE,
        },
        "dev_eval": "builtin lightweight metric evaluator on dev split",
        "holdout_eval": "builtin lightweight metric evaluator on holdout split",
        "promotion_policy": "dev_and_holdout_improved",
    }


def eval_result(split: str, *, value: float | None | object = None) -> dict[str, Any]:
    if value is None and split in {"dev", "holdout"}:
        value = 4.0 if split == "dev" else 4.5
    return {
        "schema_version": "auto_research_lightweight_eval_result_v0",
        "split": split,
        "metric": {
            "name": METRIC_NAME,
            "direction": "maximize",
            "value": value,
            "baseline": BASELINE,
        },
        "eval_status": "scored",
        "primary_metric_status": "improved",
        "artifact_refs": [f"public_metric:{split}:state_a2a_round"],
        "protected_scope_clean": True,
        "no_upload": True,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_contract_and_results(temp: Path) -> tuple[Path, Path, Path]:
    contract = temp / "research-contract.public.json"
    dev = temp / "dev-result.public.json"
    holdout = temp / "holdout-result.public.json"
    write_json(contract, research_contract())
    write_json(dev, eval_result("dev"))
    write_json(holdout, eval_result("holdout"))
    return contract, dev, holdout
