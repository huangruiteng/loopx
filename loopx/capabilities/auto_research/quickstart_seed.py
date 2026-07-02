"""Small starter-pack seed for the current auto-research worker smoke path.

This module is intentionally narrow: it preserves the existing public k-NN
starter behavior without making the worker runtime depend on legacy demo code.
The product kernel should continue to move toward injected frontier/action/
evidence adapters rather than adding more template families here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .evidence_packet import (
    RESEARCH_CONTRACT_SCHEMA_VERSION,
    RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
    validate_research_contract,
    validate_research_hypothesis,
)


AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION = "auto_research_quickstart_v0"
AUTO_RESEARCH_DEFAULT_GOAL_ID = "loopx-auto-research-knn"
AUTO_RESEARCH_DEFAULT_OBJECTIVE = "Improve exact k-nearest-neighbor inference under a protected evaluator."
AUTO_RESEARCH_QUICKSTART_TEMPLATE = "knn-exact"


def _compact_token(value: object, *, field: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._:-]+", "-", str(value or "")).strip("-._:")
    if not text:
        raise ValueError(f"{field} must be a non-empty public token")
    return text[:120]


def _compact_text(value: object, *, field: str, max_len: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError(f"{field} must be non-empty")
    return text[:max_len]


def _relative_pack_dir(value: object) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError("output_dir is required")
    pack_dir = Path(text)
    if pack_dir.is_absolute() or ".." in pack_dir.parts:
        raise ValueError("output_dir must be a relative path inside the workspace")
    return pack_dir


def _quickstart_contract(*, goal_id: str, objective: str) -> dict[str, Any]:
    contract = validate_research_contract(
        {
            "schema_version": RESEARCH_CONTRACT_SCHEMA_VERSION,
            "goal_id": goal_id,
            "research_objective": objective,
            "editable_scope": ["solution_candidate.py"],
            "protected_scope": [
                "protected_eval.py",
                "solution_baseline.py",
                "research_contract.json",
            ],
            "metric": {
                "name": "deterministic_speedup",
                "direction": "maximize",
                "baseline": 1.0,
            },
            "dev_eval": "python3 protected_eval.py --solution solution_candidate.py --split dev",
            "holdout_eval": "python3 protected_eval.py --solution solution_candidate.py --split holdout",
            "promotion_policy": "requires_dev_and_holdout_improvement_exactness_and_clean_boundary",
        }
    )
    contract["no_upload"] = True
    return contract


_QUICKSTART_PROTECTED_EVAL = '''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

SCHEMA_VERSION = "auto_research_knn_eval_result_v0"
PACK_DIR = Path(__file__).resolve().parent
Point = tuple[float, ...]
SPLITS = {
    "dev": {"metric": 4.0, "train_count": 6, "query_count": 2, "k": 2},
    "holdout": {"metric": 4.5, "train_count": 8, "query_count": 3, "k": 2},
}


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def _points(count: int, *, offset: float) -> list[Point]:
    return [(float(index), float((index * 7) % 5) + offset) for index in range(count)]


def _oracle(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    expected: list[list[int]] = []
    for query in queries:
        ranked = sorted((_squared_distance(query, point), index) for index, point in enumerate(train))
        expected.append([index for _, index in ranked[:k]])
    return expected


def _load_solution(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("auto_research_knn_solution", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load solution from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "solve_knn"):
        raise ValueError("solution must define solve_knn(train, queries, k)")
    return module


def evaluate(solution_path: Path, split: str) -> dict[str, Any]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    spec = SPLITS[split]
    solution_path = solution_path.resolve()
    module = _load_solution(solution_path)
    train = _points(spec["train_count"], offset=0.0)
    queries = _points(spec["query_count"], offset=0.25)
    k = spec["k"]
    expected = _oracle(train, queries, k)
    actual = module.solve_knn(train, queries, k)
    exact = actual == expected
    strategy = str(getattr(module, "STRATEGY", "unknown"))
    protected_scope_clean = solution_path.parent == PACK_DIR and solution_path.name in {
        "solution_baseline.py",
        "solution_candidate.py",
    }
    improved = exact and strategy == "partial_selection"
    metric_value = spec["metric"] if improved else (1.0 if exact else None)
    promotion_ready = bool(metric_value is not None and metric_value > 1.0 and protected_scope_clean)
    return {
        "schema_version": SCHEMA_VERSION,
        "split": split,
        "solution": solution_path.name,
        "strategy": strategy,
        "dataset": {
            "train_count": spec["train_count"],
            "query_count": spec["query_count"],
            "k": k,
        },
        "metric": {
            "name": "deterministic_speedup",
            "direction": "maximize",
            "value": metric_value,
            "baseline": 1.0,
        },
        "exact": exact,
        "protected_scope_clean": protected_scope_clean,
        "no_upload": True,
        "eval_status": "scored" if exact else "guardrail_failed",
        "primary_metric_status": "improved" if improved else ("baseline" if exact else "failed"),
        "promotion_gate": {
            "requires": [
                "exact_neighbor_identity",
                "dev_and_holdout_improvement",
                "protected_scope_clean",
                "no_upload",
            ],
            "ready_for_split": promotion_ready,
        },
        "artifact_refs": [f"knn_seed:{split}:{strategy}"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Protected evaluator for the public LoopX auto-research k-NN seed.")
    parser.add_argument("--solution", required=True, help="Path to a solution module.")
    parser.add_argument("--split", choices=sorted(SPLITS), required=True)
    args = parser.parse_args()
    payload = evaluate(Path(args.solution), args.split)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["exact"] and payload["protected_scope_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


_QUICKSTART_SOLUTION_BASELINE = '''from __future__ import annotations


STRATEGY = "full_sort"
Point = tuple[float, ...]


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def solve_knn(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    results: list[list[int]] = []
    for query in queries:
        ranked = sorted((_squared_distance(query, point), index) for index, point in enumerate(train))
        results.append([index for _, index in ranked[:k]])
    return results
'''


_QUICKSTART_SOLUTION_CANDIDATE = '''from __future__ import annotations

import heapq


STRATEGY = "partial_selection"
Point = tuple[float, ...]


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def solve_knn(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    results: list[list[int]] = []
    for query in queries:
        nearest = heapq.nsmallest(
            k,
            ((_squared_distance(query, point), index) for index, point in enumerate(train)),
        )
        results.append([index for _, index in nearest])
    return results
'''


_QUICKSTART_README = '''# LoopX Auto Research k-NN Seed

This public-safe seed exists for the current worker smoke path. Edit only
`solution_candidate.py`; keep `protected_eval.py`, `solution_baseline.py`, and
`research_contract.json` unchanged.
'''


def _quickstart_template_files(contract: dict[str, Any]) -> dict[str, str]:
    return {
        "research_contract.json": json.dumps(contract, indent=2, sort_keys=True) + "\n",
        "protected_eval.py": _QUICKSTART_PROTECTED_EVAL,
        "solution_baseline.py": _QUICKSTART_SOLUTION_BASELINE,
        "solution_candidate.py": _QUICKSTART_SOLUTION_CANDIDATE,
        "README.md": _QUICKSTART_README,
    }


def _quickstart_file_summary(
    *,
    pack_dir: Path,
    files: dict[str, str],
    write_status: str,
) -> list[dict[str, Any]]:
    protected_names = {"protected_eval.py", "solution_baseline.py", "research_contract.json"}
    role_by_name = {
        "README.md": "operator_notes",
        "protected_eval.py": "protected_evaluator",
        "research_contract.json": "research_contract",
        "solution_baseline.py": "protected_baseline",
        "solution_candidate.py": "editable_candidate",
    }
    return [
        {
            "path": f"{pack_dir.as_posix()}/{name}",
            "role": role_by_name.get(name, "pack_file"),
            "protected": name in protected_names,
            "write_status": write_status,
        }
        for name in sorted(files)
    ]


def build_auto_research_quickstart(
    *,
    agent_id: str,
    goal_id: str = AUTO_RESEARCH_DEFAULT_GOAL_ID,
    objective: str = AUTO_RESEARCH_DEFAULT_OBJECTIVE,
    output_dir: str = "auto_research_knn_pack",
    template: str = AUTO_RESEARCH_QUICKSTART_TEMPLATE,
    execute: bool = False,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Preview or create the current public k-NN starter pack."""

    agent = _compact_token(agent_id, field="agent_id")
    goal = _compact_token(goal_id, field="goal_id")
    objective_text = _compact_text(objective, field="objective")
    selected_template = _compact_token(template, field="template")
    if selected_template != AUTO_RESEARCH_QUICKSTART_TEMPLATE:
        raise ValueError(f"template must be {AUTO_RESEARCH_QUICKSTART_TEMPLATE}")
    pack_dir = _relative_pack_dir(output_dir)
    contract = _quickstart_contract(goal_id=goal, objective=objective_text)
    files = _quickstart_template_files(contract)
    dev_command = (
        f"python3 {pack_dir.as_posix()}/protected_eval.py "
        f"--solution {pack_dir.as_posix()}/solution_candidate.py --split dev"
    )
    holdout_command = (
        f"python3 {pack_dir.as_posix()}/protected_eval.py "
        f"--solution {pack_dir.as_posix()}/solution_candidate.py --split holdout"
    )
    hypothesis = validate_research_hypothesis(
        {
            "schema_version": RESEARCH_HYPOTHESIS_SCHEMA_VERSION,
            "hypothesis_id": "hyp_quickstart_partial_selection",
            "todo_id": "todo_auto_research_quickstart_001",
            "claimed_by": agent,
            "mechanism_family": "partial_selection",
            "hypothesis": "Use exact partial selection to avoid full distance sorting.",
            "status": "active",
            "grounding_refs": ["quickstart:knn_exact_pack"],
            "blocked_by": [],
        }
    )
    write_status = "would_write"
    if execute:
        root = (cwd or Path.cwd()).resolve()
        target_dir = (root / pack_dir).resolve()
        try:
            target_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError("output_dir must resolve inside the current working directory") from exc
        if target_dir.exists():
            raise ValueError(f"output_dir already exists: {pack_dir.as_posix()}")
        target_dir.mkdir(parents=True)
        for name, contents in files.items():
            target = target_dir / name
            target.write_text(contents, encoding="utf-8")
            if name == "protected_eval.py":
                target.chmod(0o755)
        write_status = "created"
    return {
        "ok": True,
        "schema_version": AUTO_RESEARCH_QUICKSTART_SCHEMA_VERSION,
        "mode": "execute" if execute else "dry_run",
        "template": selected_template,
        "research_contract": contract,
        "pack_dir": pack_dir.as_posix(),
        "files": _quickstart_file_summary(
            pack_dir=pack_dir,
            files=files,
            write_status=write_status,
        ),
        "next_runnable_hypothesis": hypothesis | {
            "allowed_action": "run_dev_attempt",
            "run_command": dev_command,
        },
        "next_commands": [
            {
                "label": "create_pack",
                "command": (
                    f"loopx --format json auto-research quickstart --agent-id {agent} "
                    f"--goal-id {goal} --output-dir {pack_dir.as_posix()} --execute"
                ),
                "required_when": "dry_run",
            },
            {"label": "run_dev", "command": dev_command},
            {"label": "run_holdout", "command": holdout_command},
        ],
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "source": "generated_public_quickstart_seed",
        },
    }
