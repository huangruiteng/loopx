#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

SCHEMA_VERSION = "auto_research_knn_eval_result_v0"
PACK_DIR = Path(__file__).resolve().parent
Point = tuple[float, ...]

SPLITS: dict[str, dict[str, int]] = {
    "dev": {"seed": 17, "train_count": 256, "query_count": 18, "dims": 4, "k": 3},
    "holdout": {"seed": 31, "train_count": 512, "query_count": 24, "dims": 4, "k": 3},
}


def _point(seed: int, index: int, dims: int) -> Point:
    values = []
    for dim in range(dims):
        raw = (seed * (dim + 5) + index * (dim * 23 + 11) + index * index * (dim + 3)) % 997
        values.append(raw / 97.0)
    return tuple(values)


def build_split(split: str) -> tuple[list[Point], list[Point], int, dict[str, int]]:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    spec = SPLITS[split]
    train = [_point(spec["seed"], index, spec["dims"]) for index in range(spec["train_count"])]
    queries = [
        _point(spec["seed"] + 101, index, spec["dims"])
        for index in range(spec["query_count"])
    ]
    return train, queries, spec["k"], spec


def _squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def oracle_knn(train: list[Point], queries: list[Point], k: int) -> list[list[int]]:
    expected: list[list[int]] = []
    for query in queries:
        ranked = sorted((_squared_distance(query, point), index) for index, point in enumerate(train))
        expected.append([index for _, index in ranked[:k]])
    return expected


def load_solution(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("auto_research_knn_solution", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load solution from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "solve_knn"):
        raise ValueError("solution must define solve_knn(train, queries, k)")
    return module


def ranking_work_units(strategy: str, *, train_count: int, query_count: int, k: int) -> int:
    if strategy == "partial_selection":
        rank_factor = max(1, math.ceil(math.log2(k + 1)))
    else:
        rank_factor = max(1, math.ceil(math.log2(train_count)))
    return query_count * train_count * rank_factor


def evaluate(solution_path: Path, split: str) -> dict[str, Any]:
    solution_path = solution_path.resolve()
    train, queries, k, spec = build_split(split)
    module = load_solution(solution_path)
    strategy = str(getattr(module, "STRATEGY", "unknown"))
    expected = oracle_knn(train, queries, k)
    actual = module.solve_knn(train, queries, k)
    exact = actual == expected

    baseline_units = ranking_work_units(
        "full_sort",
        train_count=spec["train_count"],
        query_count=spec["query_count"],
        k=k,
    )
    candidate_units = ranking_work_units(
        strategy,
        train_count=spec["train_count"],
        query_count=spec["query_count"],
        k=k,
    )
    speedup = baseline_units / candidate_units if exact else None
    improved = bool(speedup is not None and speedup > 1.0)
    protected_scope_clean = solution_path.parent == PACK_DIR and solution_path.name in {
        "solution_baseline.py",
        "solution_candidate.py",
    }
    promotion_ready = exact and improved and protected_scope_clean
    return {
        "schema_version": SCHEMA_VERSION,
        "split": split,
        "solution": solution_path.name,
        "strategy": strategy,
        "dataset": {
            "train_count": spec["train_count"],
            "query_count": spec["query_count"],
            "dims": spec["dims"],
            "k": k,
            "seed": spec["seed"],
        },
        "metric": {
            "name": "deterministic_speedup",
            "direction": "maximize",
            "value": round(speedup, 6) if speedup is not None else None,
            "baseline": 1.0,
        },
        "work_units": {
            "baseline_full_sort": baseline_units,
            "candidate": candidate_units,
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
        "artifact_refs": [
            f"knn_pack:{split}:{strategy}",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Protected evaluator for the public LoopX auto-research k-NN pack.")
    parser.add_argument("--solution", required=True, help="Path to a solution module.")
    parser.add_argument("--split", choices=sorted(SPLITS), required=True)
    args = parser.parse_args()
    payload = evaluate(Path(args.solution), args.split)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["exact"] and payload["protected_scope_clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
