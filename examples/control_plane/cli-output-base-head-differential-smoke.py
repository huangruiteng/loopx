#!/usr/bin/env python3
"""Compare agent-facing CLI output from one public fixture on base and head."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.cli_output_differential import (  # noqa: E402
    compare_cli_output_receipts,
)


PROBE_TEST = REPO_ROOT / "tests" / "control_plane" / "test_cli_output_budget.py"
PROBE_RUNNER = REPO_ROOT / "examples" / "control_plane" / "cli-output-probe-runner.py"
SEMANTICS_SOURCE = (
    REPO_ROOT / "loopx" / "control_plane" / "testing" / "cli_output_semantics.py"
)


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=240,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout[-4000:]}\n"
            f"stderr:\n{completed.stderr[-4000:]}"
        )


def _run_probe(
    *,
    source_root: Path,
    probe_runner: Path,
    probe_test: Path,
    semantics_source: Path,
    fixture_root: Path,
    receipt_path: Path,
    cwd: Path,
) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_root)
    _run(
        [
            sys.executable,
            str(probe_runner),
            "--test-source",
            str(probe_test),
            "--semantics-source",
            str(semantics_source),
            "--fixture-root",
            str(fixture_root),
            "--receipt",
            str(receipt_path),
        ],
        cwd=cwd,
        env=env,
    )


def _load_receipt(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"probe receipt must be an object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("LOOPX_CLI_OUTPUT_BASE_REF", "origin/main"),
    )
    args = parser.parse_args()
    if not PROBE_TEST.is_file():
        raise RuntimeError(f"missing probe source: {PROBE_TEST.relative_to(REPO_ROOT)}")
    if not PROBE_RUNNER.is_file():
        raise RuntimeError(
            f"missing probe runner: {PROBE_RUNNER.relative_to(REPO_ROOT)}"
        )
    if not SEMANTICS_SOURCE.is_file():
        raise RuntimeError(
            f"missing probe semantics: {SEMANTICS_SOURCE.relative_to(REPO_ROOT)}"
        )

    with tempfile.TemporaryDirectory(prefix="loopx-cli-output-differential-") as temp:
        temp_root = Path(temp)
        base_root = temp_root / "base"
        probe_test = temp_root / "test_cli_output_probe.py"
        probe_runner = temp_root / "cli_output_probe_runner.py"
        semantics_source = temp_root / "cli_output_semantics.py"
        fixture_root = temp_root / "public-fixture"
        base_receipt = temp_root / "base-receipt.json"
        candidate_receipt = temp_root / "candidate-receipt.json"
        shutil.copy2(PROBE_TEST, probe_test)
        shutil.copy2(PROBE_RUNNER, probe_runner)
        shutil.copy2(SEMANTICS_SOURCE, semantics_source)

        _run(
            ["git", "worktree", "add", "--detach", str(base_root), args.base_ref],
            cwd=REPO_ROOT,
        )
        try:
            _run_probe(
                source_root=base_root,
                probe_runner=probe_runner,
                probe_test=probe_test,
                semantics_source=semantics_source,
                fixture_root=fixture_root,
                receipt_path=base_receipt,
                cwd=temp_root,
            )
            _run_probe(
                source_root=REPO_ROOT,
                probe_runner=probe_runner,
                probe_test=probe_test,
                semantics_source=semantics_source,
                fixture_root=fixture_root,
                receipt_path=candidate_receipt,
                cwd=temp_root,
            )
        finally:
            _run(
                ["git", "worktree", "remove", "--force", str(base_root)],
                cwd=REPO_ROOT,
            )

        comparison = compare_cli_output_receipts(
            _load_receipt(base_receipt),
            _load_receipt(candidate_receipt),
        )
        if not comparison["ok"]:
            failed = [
                {"row_id": row["row_id"], "failures": row["failures"]}
                for row in comparison["rows"]
                if row["status"] == "failed"
            ]
            raise AssertionError(
                "agent-facing CLI base/head differential failed\n"
                + json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True)
            )
        if comparison["review_required"]:
            review_signals = [
                {"row_id": row["row_id"], "review_signals": row["review_signals"]}
                for row in comparison["rows"]
                if row["review_signals"]
            ]
            print(
                "cli-output-base-head-differential review-signals "
                + json.dumps(review_signals, ensure_ascii=False, sort_keys=True)
            )
        print(
            "cli-output-base-head-differential-smoke ok "
            f"base={comparison['base_row_count']} "
            f"candidate={comparison['candidate_row_count']} "
            f"candidate_only={comparison['candidate_only_row_count']} "
            f"review_required={comparison['review_row_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
