#!/usr/bin/env python3
"""Smoke-test the default-off ML experiment domain capability pack."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.ml_experiment import (  # noqa: E402
    DATASET_WINDOW_CONTRACT_SCHEMA_VERSION,
    EXPERIMENT_REPLAN_SCHEMA_VERSION,
    HYPOTHESIS_LEDGER_SCHEMA_VERSION,
    ML_EXPERIMENT_ADVISORY_PACKET_SCHEMA_VERSION,
    ML_EXPERIMENT_RESULT_SCHEMA_VERSION,
    build_ml_experiment_advisory_packet,
)


def assert_no_private_surface(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "private/",
        "/" + "tmp/",
        "lark" + "office",
        "byte" + "dance",
        "http://",
        "https://",
        "s3://",
        "tos://",
        "hdfs://",
        "api" + "_key",
        "pass" + "word",
        "sec" + "ret",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in text.lower()]
    assert not leaked, leaked


def run_cli(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> None:
    packet = build_ml_experiment_advisory_packet(
        experiment_id="exp_preview_v1",
        primary_metric="offline_auc",
        baseline_value=0.421,
        candidate_value=0.437,
        guardrail_status="clean",
        train_window="train_2026w24",
        eval_window="eval_2026w25",
        hypothesis_id="h_route_mix_v1",
        mechanism_family="candidate retrieval mix",
        route="route_mix",
        positive_evidence=["offline_eval_delta_positive"],
        negative_evidence=["serving_latency_unknown"],
        next_candidates=["holdout_eval", "latency_guardrail_probe"],
    )
    assert packet["schema_version"] == ML_EXPERIMENT_ADVISORY_PACKET_SCHEMA_VERSION, packet
    assert packet["pack"]["enabled"] is False, packet
    assert packet["pack"]["autonomy"] == "suggest_only", packet
    assert packet["launch_actions_enabled"] is False, packet
    assert packet["production_actions_enabled"] is False, packet
    assert packet["result"]["schema_version"] == ML_EXPERIMENT_RESULT_SCHEMA_VERSION, packet
    assert packet["result"]["primary_metric_status"] == "improved", packet
    assert packet["result"]["decision_status"] == "candidate_not_winner_yet", packet
    assert packet["result"]["dataset_window"]["schema_version"] == DATASET_WINDOW_CONTRACT_SCHEMA_VERSION, packet
    assert packet["result"]["hypothesis"]["schema_version"] == HYPOTHESIS_LEDGER_SCHEMA_VERSION, packet
    assert packet["replan_preview"]["schema_version"] == EXPERIMENT_REPLAN_SCHEMA_VERSION, packet
    assert packet["replan_preview"]["launch_actions_enabled"] is False, packet
    assert_no_private_surface(packet)

    result = run_cli(
        [
            "--format",
            "json",
            "ml-experiment",
            "preview",
            "--experiment-id",
            "exp_preview_v1",
            "--primary-metric",
            "offline_auc",
            "--baseline-value",
            "0.421",
            "--candidate-value",
            "0.437",
            "--guardrail-status",
            "clean",
            "--train-window",
            "train_2026w24",
            "--eval-window",
            "eval_2026w25",
            "--hypothesis-id",
            "h_route_mix_v1",
            "--mechanism-family",
            "candidate retrieval mix",
            "--route",
            "route_mix",
            "--positive-evidence",
            "offline_eval_delta_positive",
            "--negative-evidence",
            "serving_latency_unknown",
            "--next-candidate",
            "holdout_eval",
        ]
    )
    payload = json.loads(result.stdout)
    assert payload["ok"], payload
    assert payload["schema_version"] == ML_EXPERIMENT_ADVISORY_PACKET_SCHEMA_VERSION, payload
    assert payload["pack"]["enabled"] is False, payload
    assert payload["result"]["primary_metric_status"] == "improved", payload
    assert_no_private_surface(payload)

    blocked = run_cli(
        [
            "--format",
            "json",
            "ml-experiment",
            "preview",
            "--experiment-id",
            "exp_preview_v1",
            "--primary-metric",
            "offline_auc",
            "--baseline-value",
            "0.421",
            "--candidate-value",
            "0.437",
            "--train-window",
            "/" + "Users/example/private/train.log",
            "--eval-window",
            "eval_2026w25",
            "--hypothesis-id",
            "h_route_mix_v1",
            "--mechanism-family",
            "candidate retrieval mix",
            "--route",
            "route_mix",
        ],
        check=False,
    )
    assert blocked.returncode == 1, blocked.stdout
    blocked_payload = json.loads(blocked.stdout)
    assert blocked_payload["ok"] is False, blocked_payload
    assert "public alias" in blocked_payload["error"], blocked_payload

    docs = (REPO_ROOT / "docs" / "product" / "domain-capability-packs.md").read_text(encoding="utf-8")
    assert "loopx ml-experiment preview" in docs, docs
    assert "launch_actions_enabled=false" in docs, docs
    assert "production_actions_enabled=false" in docs, docs

    print("ml-experiment-domain-pack-smoke ok")


if __name__ == "__main__":
    main()
