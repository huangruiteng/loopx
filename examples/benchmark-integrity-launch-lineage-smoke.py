#!/usr/bin/env python3
"""Smoke-test deterministic benchmark launch-lineage qualification."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.benchmark_toolkit import (  # noqa: E402
    BENCHMARK_RUNTIME_INTEGRITY_ATTESTATION_V1_SCHEMA_VERSION,
    EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION,
    REQUIRED_RUNTIME_ATTESTATIONS,
    benchmark_integrity_policy_sha256,
    build_benchmark_launch_admission_receipt,
    build_benchmark_trajectory_lineage_receipt,
    build_traex_model_route_receipt,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_sha(value: object) -> str:
    return _sha(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _strict_inputs() -> tuple[dict[str, object], tuple[str, ...]]:
    instruction = "private fixture instruction"
    containment_ref = "private-containment-reference"
    runtime_ref = "private-runtime-reference"
    credential = "sk-private-fixture-credential"
    private_path = "/private/benchmark/case-1"
    launch = build_benchmark_launch_admission_receipt(
        benchmark_id="fixture@v0",
        case_id="public-suite/case-1",
        run_id="run-1",
        arm_id="treatment",
        instruction_sha256=_sha(instruction),
        integrity_policy_sha256=benchmark_integrity_policy_sha256(None),
        expected_provider="trae",
        expected_model="GPT-5.4",
        containment_binding_sha256=_sha(containment_ref),
        runtime_binding_sha256=_sha(runtime_ref),
        credential_isolation={
            "mechanism": "runner-owned-gateway",
            "authority": "runner",
            "evidence_sha256": _sha("credential-isolation"),
        },
        controller_isolation={
            "mechanism": "container-namespace",
            "authority": "runner",
            "evidence_sha256": _sha("controller-isolation"),
        },
        runner_authority="runner",
        provider_authority="provider-adapter",
        issued_at="2026-09-03T00:30:00Z",
    )
    trajectory: dict[str, object] = {
        "schema_version": "ATIF-v1.7",
        "steps": [
            {
                "step_id": "1",
                "source": "agent",
                "message": "completed",
                "tool_calls": [],
            }
        ],
    }
    result: dict[str, object] = {
        "schema_version": EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION,
        "status": "succeeded",
        "exit_code": 0,
        "receipt": {
            "schema_version": "external_agent_phase_receipt_v2",
            "classification": "solver_completed",
            "command_recorded": False,
            "command_argument_count": 2,
            "duration_ms": 10,
            "instruction_recorded": False,
            "workspace_recorded": False,
            "instruction_sha256": launch["instruction_sha256"],
            "instruction_chars": len(instruction),
            "launch_binding_digest": launch["launch_binding_digest"],
        },
    }
    attestation = {
        "schema_version": (BENCHMARK_RUNTIME_INTEGRITY_ATTESTATION_V1_SCHEMA_VERSION),
        "authority": launch["runner_authority"],
        **{
            field: launch[field]
            for field in (
                "benchmark_id",
                "case_id",
                "run_id",
                "arm_id",
                "launch_binding_digest",
                "integrity_policy_sha256",
                "containment_binding_sha256",
                "runtime_binding_sha256",
                "credential_isolation",
                "controller_isolation",
            )
        },
        **{field: True for field in REQUIRED_RUNTIME_ATTESTATIONS},
    }
    route = build_traex_model_route_receipt(
        [
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "context": {
                        "model": "GPT-5.4",
                        "modelProviderId": "trae",
                    },
                },
            }
        ],
        requested_model="GPT-5.4",
        run_id=str(launch["run_id"]),
        arm_id=str(launch["arm_id"]),
        launch_binding_digest=str(launch["launch_binding_digest"]),
        authority="provider-adapter",
    )
    lineage = build_benchmark_trajectory_lineage_receipt(
        authority="runner",
        run_id=str(launch["run_id"]),
        arm_id=str(launch["arm_id"]),
        launch_binding_digest=str(launch["launch_binding_digest"]),
        external_agent_result=result,
        trajectory=trajectory,
        containment_binding_sha256=str(launch["containment_binding_sha256"]),
        containment_termination_postcondition=("destroyed_before_result_consumption"),
        containment_absence_verified=True,
        containment_absence_evidence_sha256=_sha("runner absence evidence"),
    )
    return (
        {
            "trajectory": trajectory,
            "trajectory_lineage_receipt": lineage,
            "external_agent_result": result,
            "runtime_attestation": attestation,
            "launch_admission_receipt": launch,
            "route_receipt": route,
        },
        (instruction, containment_ref, runtime_ref, credential, private_path),
    )


def _run_qualification(
    root: Path,
    inputs: dict[str, object],
    private_values: tuple[str, ...],
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    option_by_input = {
        "trajectory": "--trajectory-json",
        "runtime_attestation": "--runtime-attestation-json",
        "launch_admission_receipt": "--launch-admission-json",
        "route_receipt": "--route-receipt-json",
        "external_agent_result": "--external-agent-result-json",
        "trajectory_lineage_receipt": "--trajectory-lineage-receipt-json",
    }
    argv = [
        str(REPO_ROOT / "scripts" / "loopx"),
        "benchmark",
        "integrity-qualification",
    ]
    for input_name, option in option_by_input.items():
        path = root / f"private-{input_name.replace('_', '-')}.json"
        path.write_text(
            json.dumps(inputs[input_name], ensure_ascii=False),
            encoding="utf-8",
        )
        argv.extend([option, str(path)])

    env = {**os.environ, "LOOPX_PYTHON": sys.executable}
    for index, value in enumerate(private_values):
        env_name = f"LOOPX_BENCHMARK_SMOKE_PRIVATE_{index}"
        env[env_name] = value
        argv.extend(["--sensitive-value-env", env_name])
    argv.extend(["--require-qualified", "--format", "json"])
    completed = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    rendered = completed.stdout + completed.stderr
    launch = inputs["launch_admission_receipt"]
    external_result = inputs["external_agent_result"]
    assert isinstance(launch, dict), launch
    for private_value in (
        *private_values,
        str(root),
        launch["launch_binding_digest"],
        launch["instruction_sha256"],
        launch["containment_binding_sha256"],
        _canonical_sha(external_result),
    ):
        assert str(private_value) not in rendered, private_value
    return completed, json.loads(completed.stdout)


def main() -> int:
    inputs, private_values = _strict_inputs()
    with tempfile.TemporaryDirectory(prefix="loopx-benchmark-lineage-smoke-") as tmp:
        root = Path(tmp)
        completed, receipt = _run_qualification(root, inputs, private_values)
        assert completed.returncode == 0, completed.stderr or completed.stdout
        assert receipt["integrity_qualified"] is True, receipt
        assert receipt["launch_lineage"]["qualified"] is True, receipt
        assert receipt["public_boundary"]["input_paths_recorded"] is False, receipt

        mutated = deepcopy(inputs)
        mutated["route_receipt"]["run_id"] = "run-other"
        rejected_run, rejected = _run_qualification(root, mutated, private_values)
        assert rejected_run.returncode == 1, rejected_run.stderr or rejected_run.stdout
        assert rejected["integrity_qualified"] is False, rejected
        assert rejected["classification"] == "launch_lineage_not_qualified", rejected
        assert "route_receipt_run_id_mismatch" in rejected["blockers"], rejected

    print("benchmark integrity launch-lineage smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
