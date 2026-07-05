from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path


KNN_DEMO_WORKSPACE_SCHEMA_VERSION = "loopx_knn_demo_workspace_v0"

KNN_DEMO_EDITABLE_SCOPE = ["solution.py"]
KNN_DEMO_PROTECTED_SCOPE = ["task.py", "eval.py", "eval.sh"]
KNN_DEMO_CONTRACT_FILE = "research_contract.public.json"
KNN_DEMO_DEV_EVAL_COMMAND = "bash eval.sh dev"
KNN_DEMO_HOLDOUT_EVAL_COMMAND = "bash eval.sh test"


README_MD = """# LoopX KNN Auto-Research Demo

Goal: improve exact k-nearest-neighbor search speed while preserving correctness.

Editable scope:
- `solution.py`

Protected scope:
- `task.py`
- `eval.py`
- `eval.sh`

Commands:
- `bash eval.sh dev`
- `bash eval.sh test`

Evidence rule:
- Record the command, split, score, mechanism, and changed file before claiming an improvement.
- Do not edit protected files to improve the score.

Recording-friendly artifact checklist:
- Curator: metric, editable/protected boundary, and promotion rule.
- Hypothesis proposer: two exact-KNN speedup hypotheses with mechanism and risk.
- Executor: baseline dev score, changed mechanism, post-change dev score, and held-out score when dev improves.
- Evaluator: split-aware verdict and the next role todo or retry reason.
"""


AGENTS_MD = """# KNN Demo Agent Rules

Only edit `solution.py`.

Do not edit `task.py`, `eval.py`, or `eval.sh`.

Run `bash eval.sh dev` for development evidence and `bash eval.sh test` for held-out evidence.

For visible auto-research, do not stop at a status/tick summary. Leave one compact
public-safe artifact, todo update, or evidence packet that another role can use.
"""


TASK_PY = '''from __future__ import annotations

from random import Random


K = 7
DIM = 12


def _sizes(split: str) -> tuple[int, int, int]:
    if split == "test":
        return 4, 1800, 100
    return 4, 1400, 80


def _seed(split: str) -> int:
    return 9001 if split == "test" else 1009


def generate_instances(split: str):
    split = "test" if str(split).strip() == "test" else "dev"
    count, database_size, query_size = _sizes(split)
    rng = Random(_seed(split))
    for _ in range(count):
        database = [
            [rng.uniform(-1.0, 1.0) for _ in range(DIM)]
            for _ in range(database_size)
        ]
        queries = [
            [rng.uniform(-1.0, 1.0) for _ in range(DIM)]
            for _ in range(query_size)
        ]
        yield {"database": database, "queries": queries, "k": K}


def squared_distance(left, right) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def reference_solve(problem):
    database = problem["database"]
    k = int(problem["k"])
    output = []
    for query in problem["queries"]:
        ranked = sorted(
            (squared_distance(row, query), index)
            for index, row in enumerate(database)
        )
        output.append([index for _distance, index in ranked[:k]])
    return output


def is_solution(problem, candidate) -> bool:
    return candidate == reference_solve(problem)
'''


SOLUTION_PY = '''from __future__ import annotations


def _squared_distance(left, right) -> float:
    return sum((a - b) * (a - b) for a, b in zip(left, right))


def solve(problem):
    """Baseline exact KNN: full-sort every query."""

    database = problem["database"]
    k = int(problem["k"])
    output = []
    for query in problem["queries"]:
        ranked = sorted(
            (_squared_distance(row, query), index)
            for index, row in enumerate(database)
        )
        output.append([index for _distance, index in ranked[:k]])
    return output
'''


EVAL_PY = '''from __future__ import annotations

import importlib
import json
import statistics
import sys
import time

from task import generate_instances, is_solution, reference_solve


def _median_runtime(fn, problem, *, trials: int) -> tuple[float, object]:
    timings = []
    result = None
    for _ in range(trials):
        start = time.perf_counter()
        result = fn(problem)
        timings.append(time.perf_counter() - start)
    return statistics.median(timings), result


def evaluate(split: str) -> dict[str, object]:
    split = "test" if str(split).strip() == "test" else "dev"
    solution = importlib.import_module("solution")
    trials = 2 if split == "test" else 3
    speedups = []
    for problem in generate_instances(split):
        reference_runtime, _reference = _median_runtime(
            reference_solve,
            problem,
            trials=trials,
        )
        candidate_runtime, candidate = _median_runtime(
            solution.solve,
            problem,
            trials=trials,
        )
        if not is_solution(problem, candidate):
            return {
                "ok": False,
                "split": split,
                "score": 0.0,
                "metric_name": "speedup",
                "error": "candidate output does not match exact reference",
            }
        speedups.append(reference_runtime / max(candidate_runtime, 1e-12))
    return {
        "ok": True,
        "split": split,
        "score": round(float(statistics.median(speedups)), 6),
        "metric_name": "speedup",
        "direction": "maximize",
        "baseline_score": 1.0,
        "editable_scope": ["solution.py"],
        "protected_scope": ["task.py", "eval.py", "eval.sh"],
    }


def main(argv: list[str]) -> int:
    payload = evaluate(argv[1] if len(argv) > 1 else "dev")
    print(f"score: {payload['score']:.6f}")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
'''


EVAL_SH = """#!/usr/bin/env bash
set -euo pipefail
python3 eval.py "${1:-dev}"
"""


GITIGNORE = """__pycache__/
*.pyc
.loopx/
"""


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _contract_payload(*, goal_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "auto_research_benchmark_contract_v0",
        "preset_id": "knn-demo",
        "objective": "Improve exact KNN speedup while preserving correctness.",
        "metric": {
            "name": "speedup",
            "direction": "maximize",
            "baseline": 1.0,
        },
        "editable_scope": list(KNN_DEMO_EDITABLE_SCOPE),
        "protected_scope": list(KNN_DEMO_PROTECTED_SCOPE),
        "protected_scope_sha256": {
            "task.py": _sha256_text(TASK_PY),
            "eval.py": _sha256_text(EVAL_PY),
            "eval.sh": _sha256_text(EVAL_SH),
        },
        "dev_eval_command": KNN_DEMO_DEV_EVAL_COMMAND,
        "holdout_eval_command": KNN_DEMO_HOLDOUT_EVAL_COMMAND,
        "claim_boundary": (
            "Claims require command output from the generated benchmark workspace; "
            "do not edit protected files."
        ),
    }
    if goal_id:
        payload["goal_id"] = goal_id
    return payload


def _write_if_missing(path: Path, content: str, *, executable: bool = False) -> bool:
    if path.exists():
        if executable:
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return False
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return True


def materialize_knn_demo_workspace(workspace: str | Path, *, goal_id: str | None = None) -> dict[str, object]:
    """Create the real KNN demo benchmark workspace if it is missing."""

    workspace_path = Path(workspace).expanduser()
    created = not workspace_path.exists()
    workspace_path.mkdir(parents=True, exist_ok=True)

    files = {
        "README.md": README_MD,
        "AGENTS.md": AGENTS_MD,
        "task.py": TASK_PY,
        "solution.py": SOLUTION_PY,
        "eval.py": EVAL_PY,
        "eval.sh": EVAL_SH,
        ".gitignore": GITIGNORE,
    }
    written: list[str] = []
    kept: list[str] = []
    for relative_path, content in files.items():
        path = workspace_path / relative_path
        did_write = _write_if_missing(
            path,
            content,
            executable=relative_path == "eval.sh",
        )
        (written if did_write else kept).append(relative_path)

    contract_path = workspace_path / KNN_DEMO_CONTRACT_FILE
    contract_path.write_text(
        json.dumps(_contract_payload(goal_id=goal_id), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    marker_path = workspace_path / ".loopx-knn-demo-workspace.public.json"
    marker = {
        "schema_version": KNN_DEMO_WORKSPACE_SCHEMA_VERSION,
        "preset_id": "knn-demo",
        "goal_id": goal_id or "",
        "workspace_created": created,
        "contract_file": KNN_DEMO_CONTRACT_FILE,
        "editable_scope": list(KNN_DEMO_EDITABLE_SCOPE),
        "protected_scope": list(KNN_DEMO_PROTECTED_SCOPE),
        "dev_eval_command": KNN_DEMO_DEV_EVAL_COMMAND,
        "holdout_eval_command": KNN_DEMO_HOLDOUT_EVAL_COMMAND,
        "files_written": written,
        "files_kept": kept,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
        },
    }
    marker_path.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return marker
