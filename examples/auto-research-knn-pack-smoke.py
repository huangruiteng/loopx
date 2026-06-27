#!/usr/bin/env python3
"""Smoke-test the public runnable auto-research k-NN pack."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = REPO_ROOT / "examples/auto_research_knn_pack"
EVAL = PACK / "protected_eval.py"
BASELINE = PACK / "solution_baseline.py"
CANDIDATE = PACK / "solution_candidate.py"
CONTRACT = PACK / "research_contract.json"


def run_eval(solution: Path, split: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(EVAL), "--solution", str(solution), "--split", split],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def assert_public_safe(payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema_version"] == "research_contract_v0", contract
    assert contract["editable_scope"] == ["solution_candidate.py"], contract
    assert "protected_eval.py" in contract["protected_scope"], contract
    assert not set(contract["editable_scope"]).intersection(contract["protected_scope"]), contract
    assert contract["no_upload"] is True, contract
    assert_public_safe(contract)

    baseline_dev = run_eval(BASELINE, "dev")
    candidate_dev = run_eval(CANDIDATE, "dev")
    candidate_holdout = run_eval(CANDIDATE, "holdout")

    assert baseline_dev["exact"] is True, baseline_dev
    assert baseline_dev["metric"]["value"] == 1.0, baseline_dev
    assert baseline_dev["promotion_gate"]["ready_for_split"] is False, baseline_dev

    for payload in [candidate_dev, candidate_holdout]:
        assert payload["schema_version"] == "auto_research_knn_eval_result_v0", payload
        assert payload["strategy"] == "partial_selection", payload
        assert payload["exact"] is True, payload
        assert payload["protected_scope_clean"] is True, payload
        assert payload["no_upload"] is True, payload
        assert payload["eval_status"] == "scored", payload
        assert payload["primary_metric_status"] == "improved", payload
        assert payload["metric"]["value"] > 1.0, payload
        assert payload["promotion_gate"]["ready_for_split"] is True, payload
        assert_public_safe(payload)

    assert candidate_holdout["metric"]["value"] >= candidate_dev["metric"]["value"], (
        candidate_dev,
        candidate_holdout,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        external_solution = Path(temp_dir) / "solution_candidate.py"
        external_solution.write_text(CANDIDATE.read_text(encoding="utf-8"), encoding="utf-8")
        blocked = subprocess.run(
            [sys.executable, str(EVAL), "--solution", str(external_solution), "--split", "dev"],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        blocked_payload = json.loads(blocked.stdout)
        assert blocked.returncode == 1, blocked_payload
        assert blocked_payload["exact"] is True, blocked_payload
        assert blocked_payload["protected_scope_clean"] is False, blocked_payload
        assert_public_safe(blocked_payload)

    readme = (PACK / "README.md").read_text(encoding="utf-8")
    assert "protected evaluator" in readme, readme
    assert "solution_candidate.py" in readme, readme
    assert_public_safe(readme)

    print("auto-research-knn-pack-smoke ok")


if __name__ == "__main__":
    main()
