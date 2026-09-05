from __future__ import annotations

import copy
import hashlib
import json

import pytest

from loopx.capabilities.benchmark_toolkit import (
    BENCHMARK_INTEGRITY_QUALIFICATION_SCHEMA_VERSION,
    BENCHMARK_INTEGRITY_QUALIFICATION_V1_SCHEMA_VERSION,
    BENCHMARK_RUNTIME_INTEGRITY_ATTESTATION_SCHEMA_VERSION,
    BENCHMARK_RUNTIME_INTEGRITY_ATTESTATION_V1_SCHEMA_VERSION,
    BENCHMARK_TRAJECTORY_LINEAGE_RECEIPT_SCHEMA_VERSION,
    REQUIRED_RUNTIME_ATTESTATIONS,
    benchmark_integrity_policy_sha256,
    build_benchmark_integrity_input_invalid_qualification_v1,
    build_benchmark_integrity_qualification,
    build_benchmark_launch_admission_receipt,
    build_strict_benchmark_integrity_qualification,
    build_benchmark_trajectory_lineage_receipt,
    build_traex_model_route_receipt,
    normalize_benchmark_integrity_qualification_v1,
    normalize_benchmark_trajectory_lineage_receipt,
)
from loopx.capabilities.benchmark_toolkit.external_agent import (
    EXTERNAL_AGENT_RESULT_V2_SCHEMA_VERSION,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_sha(value: object) -> str:
    return _sha(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _launch(
    *, runner_authority: str = "runner", benchmark_id: str = "fixture@v0"
) -> dict[str, object]:
    return build_benchmark_launch_admission_receipt(
        benchmark_id=benchmark_id,
        case_id="public-suite/case-1",
        run_id="run-1",
        arm_id="treatment",
        instruction_sha256=_sha("do the task"),
        integrity_policy_sha256=benchmark_integrity_policy_sha256(None),
        expected_provider="trae",
        expected_model="GPT-5.4",
        containment_binding_sha256=_sha("containment-ref"),
        runtime_binding_sha256=_sha("runtime-generation"),
        credential_isolation={
            "mechanism": "runner-owned-gateway",
            "authority": runner_authority,
            "evidence_sha256": _sha("credential-evidence"),
        },
        controller_isolation={
            "mechanism": "container-namespace",
            "authority": runner_authority,
            "evidence_sha256": _sha("controller-evidence"),
        },
        runner_authority=runner_authority,
        provider_authority="provider-adapter",
        issued_at="2026-09-03T08:30:00+08:00",
    )


def _attestation(launch: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": BENCHMARK_RUNTIME_INTEGRITY_ATTESTATION_V1_SCHEMA_VERSION,
        "authority": launch["runner_authority"],
        **{
            field: launch[field]
            for field in ("benchmark_id", "case_id", "run_id", "arm_id")
        },
        **{
            field: launch[field]
            for field in (
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


def _route(launch: dict[str, object]) -> dict[str, object]:
    return build_traex_model_route_receipt(
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


def _trajectory() -> dict[str, object]:
    return {
        "schema_version": "ATIF-v1.7",
        "steps": [
            {
                "step_id": "1",
                "source": "agent",
                "message": "done",
                "tool_calls": [],
            }
        ],
    }


def _external_agent_result(launch: dict[str, object]) -> dict[str, object]:
    return {
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
            "instruction_chars": len("do the task"),
            "launch_binding_digest": launch["launch_binding_digest"],
        },
    }


def _failed_external_agent_result(
    launch: dict[str, object], *, startup: bool
) -> dict[str, object]:
    result = _external_agent_result(launch)
    result["status"] = "failed"
    result["exit_code"] = None if startup else 7
    result["receipt"]["classification"] = (
        "solver_startup_failed" if startup else "solver_exited_nonzero"
    )
    return result


def _trajectory_lineage(
    launch: dict[str, object],
    trajectory: dict[str, object],
    external_agent_result: dict[str, object],
) -> dict[str, object]:
    receipt = build_benchmark_trajectory_lineage_receipt(
        authority=str(launch["runner_authority"]),
        run_id=str(launch["run_id"]),
        arm_id=str(launch["arm_id"]),
        launch_binding_digest=str(launch["launch_binding_digest"]),
        external_agent_result=external_agent_result,
        trajectory=trajectory,
        containment_binding_sha256=str(launch["containment_binding_sha256"]),
        containment_termination_postcondition=("destroyed_before_result_consumption"),
        containment_absence_verified=True,
        containment_absence_evidence_sha256=_sha("containment-absence-evidence"),
    )
    assert (
        receipt["schema_version"] == BENCHMARK_TRAJECTORY_LINEAGE_RECEIPT_SCHEMA_VERSION
    )
    return receipt


def test_trajectory_lineage_builder_records_runner_owned_absence_proof() -> None:
    launch = _launch(runner_authority="loopsbench")
    trajectory = _trajectory()
    result = _external_agent_result(launch)

    receipt = _trajectory_lineage(launch, trajectory, result)

    assert normalize_benchmark_trajectory_lineage_receipt(receipt) == receipt
    assert receipt["authority"] == "loopsbench"
    assert receipt["containment_binding_sha256"] == launch["containment_binding_sha256"]
    assert (
        receipt["containment_termination_postcondition"]
        == "destroyed_before_result_consumption"
    )
    assert receipt["containment_absence_verified"] is True
    assert receipt["containment_absence_evidence_sha256"] == _sha(
        "containment-absence-evidence"
    )
    assert not any(field.startswith("containment_") for field in result["receipt"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authority", 1),
        ("run_id", False),
        ("arm_id", ["treatment"]),
        ("launch_binding_digest", 1),
        ("external_agent_result_sha256", False),
        ("trajectory_sha256", None),
        ("containment_binding_sha256", 1),
        ("containment_termination_postcondition", False),
        ("containment_absence_verified", 1),
        ("containment_absence_evidence_sha256", None),
    ],
)
def test_trajectory_lineage_normalizer_rejects_non_string_or_non_boolean_scalars(
    field: str, value: object
) -> None:
    inputs = _strict_integrity_inputs()
    lineage = copy.deepcopy(inputs["trajectory_lineage_receipt"])
    lineage[field] = value

    with pytest.raises(TypeError, match=f"trajectory_lineage_{field}_invalid"):
        normalize_benchmark_trajectory_lineage_receipt(lineage)


def _strict_integrity_inputs(*, benchmark_id: str = "fixture@v0") -> dict[str, object]:
    launch = _launch(benchmark_id=benchmark_id)
    trajectory = _trajectory()
    result = _external_agent_result(launch)
    return {
        "trajectory": trajectory,
        "trajectory_lineage_receipt": _trajectory_lineage(launch, trajectory, result),
        "external_agent_result": result,
        "runtime_attestation": _attestation(launch),
        "launch_admission_receipt": launch,
        "route_receipt": _route(launch),
    }


def _strict_receipt_with_credential_probe() -> dict[str, object]:
    inputs = _strict_integrity_inputs()
    inputs["trajectory"] = {
        "schema_version": "ATIF-v1.7",
        "steps": [
            {
                "step_id": "step-1",
                "source": "agent",
                "tool_calls": [
                    {
                        "function_name": "exec_command",
                        "arguments": {"cmd": "env"},
                    }
                ],
            }
        ],
    }
    inputs["trajectory_lineage_receipt"] = _trajectory_lineage(
        inputs["launch_admission_receipt"],
        inputs["trajectory"],
        inputs["external_agent_result"],
    )
    return build_strict_benchmark_integrity_qualification(**inputs)


def test_strict_integrity_qualification_accepts_exact_bound_lineage() -> None:
    inputs = _strict_integrity_inputs()
    launch = inputs["launch_admission_receipt"]

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert (
        receipt["schema_version"] == BENCHMARK_INTEGRITY_QUALIFICATION_V1_SCHEMA_VERSION
    )
    assert normalize_benchmark_integrity_qualification_v1(receipt) == receipt
    assert receipt["integrity_qualified"] is True
    assert receipt["launch_lineage"]["qualified"] is True
    assert receipt["launch_lineage"]["external_agent_result_bound"] is True
    assert receipt["launch_lineage"]["trajectory_evidence_bound"] is True
    assert receipt["public_boundary"]["launch_binding_digest_recorded"] is False
    rendered = json.dumps(receipt)
    assert str(launch["launch_binding_digest"]) not in rendered
    assert _sha("do the task") not in rendered
    assert _sha("containment-ref") not in rendered
    assert _canonical_sha(inputs["external_agent_result"]) not in rendered


def test_strict_integrity_accepts_unmatched_declared_sensitive_value_without_leak() -> (
    None
):
    secret = "fixture-private-identity-123456"

    receipt = build_strict_benchmark_integrity_qualification(
        **_strict_integrity_inputs(),
        sensitive_values=(value for value in [secret]),
    )

    assert receipt["integrity_qualified"] is True
    assert secret not in json.dumps(receipt, sort_keys=True)


def test_strict_integrity_failure_also_emits_closed_v1() -> None:
    inputs = _strict_integrity_inputs()
    inputs["route_receipt"]["run_id"] = "run-2"

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert (
        receipt["schema_version"] == BENCHMARK_INTEGRITY_QUALIFICATION_V1_SCHEMA_VERSION
    )
    assert receipt["classification"] == "launch_lineage_not_qualified"
    assert receipt["integrity_qualified"] is False
    assert normalize_benchmark_integrity_qualification_v1(receipt) == receipt


@pytest.mark.parametrize("private_trajectory_read", [False, True])
def test_strict_integrity_input_invalid_builder_emits_closed_safe_v1(
    private_trajectory_read: bool,
) -> None:
    receipt = build_benchmark_integrity_input_invalid_qualification_v1(
        private_trajectory_read=private_trajectory_read
    )

    assert normalize_benchmark_integrity_qualification_v1(receipt) == receipt
    assert (
        receipt["schema_version"] == BENCHMARK_INTEGRITY_QUALIFICATION_V1_SCHEMA_VERSION
    )
    assert receipt["ok"] is False
    assert receipt["classification"] == "input_invalid"
    assert receipt["benchmark_id"] == "unknown"
    assert receipt["case_id"] == "unknown"
    assert receipt["policy_id"] == "unknown"
    assert receipt["blockers"] == ["benchmark_integrity_input_invalid"]
    assert receipt["evidence"] == []
    assert set(receipt["evidence_counts"].values()) == {0}
    assert set(receipt["runtime_attestation_checks"].values()) == {False}
    assert receipt["audit_coverage"] == {
        "trajectory_schema_version": "unknown",
        "step_count": 0,
        "tool_call_count": 0,
        "observation_count": 0,
        "invalid_step_count": 0,
        "invalid_tool_calls_field_count": 0,
        "invalid_tool_call_count": 0,
        "trajectory_sha256": "0" * 64,
    }
    assert (
        receipt["public_boundary"]["private_trajectory_read"] is private_trajectory_read
    )
    assert all(
        value is False
        for field, value in receipt["public_boundary"].items()
        if field != "private_trajectory_read"
    )
    assert set(receipt["launch_lineage"].values()) == {False}
    assert set(receipt["claim_boundary"].values()) == {True}


@pytest.mark.parametrize(
    ("target", "field", "value"),
    (
        (None, "ok", True),
        (None, "benchmark_id", "private-benchmark"),
        (None, "blockers", ["invalid_/private/path"]),
        ("restricted_access_review", "review_required", True),
        ("evidence_counts", "credential_probe", 1),
        ("runtime_attestation_checks", "agent_phase_isolated", True),
        ("audit_coverage", "step_count", 1),
        ("public_boundary", "raw_content_recorded", True),
        ("claim_boundary", "integrity_qualification_only", False),
        ("launch_lineage", "qualified", True),
    ),
)
def test_strict_integrity_input_invalid_normalizer_rejects_noncanonical_state(
    target: str | None, field: str, value: object
) -> None:
    receipt = copy.deepcopy(build_benchmark_integrity_input_invalid_qualification_v1())
    destination = receipt if target is None else receipt[target]
    destination[field] = value

    with pytest.raises(ValueError, match="input_invalid_state_inconsistent"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_input_invalid_rejects_non_boolean_trajectory_read() -> None:
    receipt = copy.deepcopy(build_benchmark_integrity_input_invalid_qualification_v1())
    receipt["public_boundary"]["private_trajectory_read"] = 1

    with pytest.raises(TypeError, match="private_trajectory_read_invalid"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_normal_receipt_cannot_set_ok_false() -> None:
    receipt = build_strict_benchmark_integrity_qualification(
        **_strict_integrity_inputs()
    )
    receipt["ok"] = False

    with pytest.raises(ValueError, match="countability_inconsistent"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_legacy_integrity_builder_preserves_v0_protocol() -> None:
    attestation = {
        "schema_version": BENCHMARK_RUNTIME_INTEGRITY_ATTESTATION_SCHEMA_VERSION,
        "authority": "runner",
        "benchmark_id": "fixture@v0",
        "case_id": "public-suite/case-1",
        **{field: True for field in REQUIRED_RUNTIME_ATTESTATIONS},
    }

    receipt = build_benchmark_integrity_qualification(
        trajectory=_trajectory(), runtime_attestation=attestation
    )

    assert receipt["schema_version"] == BENCHMARK_INTEGRITY_QUALIFICATION_SCHEMA_VERSION
    assert receipt["classification"] == "integrity_qualified"
    assert receipt["integrity_qualified"] is True
    assert "launch_lineage" not in receipt
    assert "launch_binding_digest_recorded" not in receipt["public_boundary"]


@pytest.mark.parametrize("field", ["policy_id", "launch_lineage"])
def test_strict_integrity_normalizer_rejects_missing_top_level_fields(
    field: str,
) -> None:
    receipt = build_strict_benchmark_integrity_qualification(
        **_strict_integrity_inputs()
    )
    receipt.pop(field)

    with pytest.raises(ValueError, match="receipt_fields_invalid"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_normalizer_rejects_unknown_top_level_field() -> None:
    receipt = build_strict_benchmark_integrity_qualification(
        **_strict_integrity_inputs()
    )
    receipt["unexpected"] = True

    with pytest.raises(ValueError, match="receipt_fields_invalid"):
        normalize_benchmark_integrity_qualification_v1(receipt)


@pytest.mark.parametrize(
    ("nested_field", "mutation"),
    (
        ("launch_lineage", ("unexpected", True)),
        ("public_boundary", ("raw_content_recorded", None)),
        ("audit_coverage", ("unexpected", 0)),
    ),
)
def test_strict_integrity_normalizer_rejects_open_nested_shapes(
    nested_field: str, mutation: tuple[str, object]
) -> None:
    receipt = copy.deepcopy(
        build_strict_benchmark_integrity_qualification(**_strict_integrity_inputs())
    )
    field, value = mutation
    if value is None:
        receipt[nested_field].pop(field)
    else:
        receipt[nested_field][field] = value

    with pytest.raises(ValueError, match=f"{nested_field}_fields_invalid"):
        normalize_benchmark_integrity_qualification_v1(receipt)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("classification", "future_state", "classification_invalid"),
        ("integrity_qualified", 1, "boolean_invalid"),
        ("score_claim_countable", "false", "boolean_invalid"),
    ),
)
def test_strict_integrity_normalizer_rejects_invalid_classification_and_booleans(
    field: str, value: object, error: str
) -> None:
    receipt = build_strict_benchmark_integrity_qualification(
        **_strict_integrity_inputs()
    )
    receipt[field] = value

    with pytest.raises((TypeError, ValueError), match=error):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_normalizer_rejects_invalid_nested_boolean() -> None:
    receipt = copy.deepcopy(
        build_strict_benchmark_integrity_qualification(**_strict_integrity_inputs())
    )
    receipt["launch_lineage"]["route_receipt_bound"] = 1

    with pytest.raises(TypeError, match="launch_lineage_boolean_invalid"):
        normalize_benchmark_integrity_qualification_v1(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("benchmark_id", "/private/operator/benchmark"),
        ("case_id", "/private/operator/case"),
        ("case_id", "suite/nested/case"),
        ("policy_id", "C:\\private\\operator\\policy.json"),
    ],
)
def test_strict_integrity_normalizer_rejects_path_like_public_ids(
    field: str, value: str
) -> None:
    receipt = build_strict_benchmark_integrity_qualification(
        **_strict_integrity_inputs()
    )
    receipt[field] = value

    with pytest.raises(ValueError, match="public_token_invalid"):
        normalize_benchmark_integrity_qualification_v1(receipt)


@pytest.mark.parametrize("field", ["step_id", "tool", "source"])
def test_strict_integrity_normalizer_rejects_path_like_evidence_labels(
    field: str,
) -> None:
    secret = "fixture-sensitive-value-123456"
    inputs = _strict_integrity_inputs()
    inputs["trajectory"] = {
        "schema_version": "ATIF-v1.7",
        "steps": [
            {
                "step_id": "step-1",
                "source": "agent",
                "tool_calls": [
                    {
                        "function_name": "exec_command",
                        "arguments": {"cmd": "env"},
                    }
                ],
                "observation": secret,
            }
        ],
    }
    inputs["trajectory_lineage_receipt"] = _trajectory_lineage(
        inputs["launch_admission_receipt"],
        inputs["trajectory"],
        inputs["external_agent_result"],
    )
    receipt = build_strict_benchmark_integrity_qualification(
        **inputs, sensitive_values=[secret]
    )
    item = next(evidence for evidence in receipt["evidence"] if field in evidence)
    item[field] = "/private/operator/value"

    with pytest.raises(ValueError, match="public_token_invalid"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_redacts_path_like_private_evidence_labels() -> None:
    secret = "fixture-sensitive-value-123456"
    private_values = (
        "/private/operator/step",
        "/private/operator/tool",
        "/private/operator/source",
    )
    inputs = _strict_integrity_inputs()
    inputs["trajectory"] = {
        "schema_version": "ATIF-v1.7",
        "steps": [
            {
                "step_id": private_values[0],
                "source": private_values[2],
                "tool_calls": [
                    {
                        "function_name": private_values[1],
                        "arguments": {"cmd": "env"},
                    }
                ],
                "observation": secret,
            }
        ],
    }
    inputs["trajectory_lineage_receipt"] = _trajectory_lineage(
        inputs["launch_admission_receipt"],
        inputs["trajectory"],
        inputs["external_agent_result"],
    )

    receipt = build_strict_benchmark_integrity_qualification(
        **inputs, sensitive_values=[secret]
    )

    rendered = json.dumps(receipt, sort_keys=True)
    assert normalize_benchmark_integrity_qualification_v1(receipt) == receipt
    assert all(private_value not in rendered for private_value in private_values)
    assert any(item["step_id"].startswith("step-") for item in receipt["evidence"])
    assert any(item.get("tool", "").startswith("tool-") for item in receipt["evidence"])
    assert any(
        item.get("source", "").startswith("source-") for item in receipt["evidence"]
    )


@pytest.mark.parametrize(
    ("target", "field", "value", "error"),
    [
        (
            None,
            "classification",
            "integrity_qualified_with_suspicion",
            "classification_state_inconsistent",
        ),
        (
            None,
            "classification",
            "credential_exposure_detected",
            "countability_inconsistent",
        ),
        (None, "blockers", ["attacker_supplied_reason"], "blockers_invalid"),
        (
            "runtime_attestation_checks",
            "agent_phase_isolated",
            False,
            "runtime_attestation_state_inconsistent",
        ),
        ("audit_coverage", "step_count", 0, "blockers_state_inconsistent"),
        (
            "audit_coverage",
            "invalid_step_count",
            1,
            "blockers_state_inconsistent",
        ),
        (
            "audit_coverage",
            "invalid_tool_calls_field_count",
            1,
            "blockers_state_inconsistent",
        ),
        ("audit_coverage", "invalid_tool_call_count", 1, "blockers_state_inconsistent"),
        (
            "audit_coverage",
            "trajectory_schema_version",
            "ATIF-v2.0",
            "blockers_state_inconsistent",
        ),
    ],
)
def test_strict_integrity_normalizer_rejects_semantically_forged_qualified_state(
    target: str | None, field: str, value: object, error: str
) -> None:
    receipt = copy.deepcopy(
        build_strict_benchmark_integrity_qualification(**_strict_integrity_inputs())
    )
    destination = receipt if target is None else receipt[target]
    destination[field] = value

    with pytest.raises(ValueError, match=error):
        normalize_benchmark_integrity_qualification_v1(receipt)


@pytest.mark.parametrize(
    ("trajectory", "count_field", "blocker"),
    [
        (
            {"schema_version": "ATIF-v1.7", "steps": ["invalid-step"]},
            "invalid_step_count",
            "trajectory_step_invalid",
        ),
        (
            {
                "schema_version": "ATIF-v1.7",
                "steps": [{"step_id": "1", "tool_calls": "invalid"}],
            },
            "invalid_tool_calls_field_count",
            "trajectory_tool_calls_invalid",
        ),
        (
            {
                "schema_version": "ATIF-v1.7",
                "steps": [{"step_id": "1", "tool_calls": ["invalid"]}],
            },
            "invalid_tool_call_count",
            "trajectory_tool_call_invalid",
        ),
    ],
)
def test_strict_integrity_structural_counts_require_matching_typed_blocker(
    trajectory: dict[str, object], count_field: str, blocker: str
) -> None:
    inputs = _strict_integrity_inputs()
    inputs["trajectory"] = trajectory
    inputs["trajectory_lineage_receipt"] = _trajectory_lineage(
        inputs["launch_admission_receipt"],
        trajectory,
        inputs["external_agent_result"],
    )

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["classification"] == "trajectory_audit_incomplete"
    assert receipt["audit_coverage"][count_field] == 1
    assert blocker in receipt["blockers"]


@pytest.mark.parametrize(
    "blocker",
    [
        "trajectory_step_invalid",
        "trajectory_tool_calls_invalid",
        "trajectory_tool_call_invalid",
    ],
)
def test_strict_integrity_normalizer_rejects_structural_blocker_without_count(
    blocker: str,
) -> None:
    receipt = copy.deepcopy(
        build_strict_benchmark_integrity_qualification(**_strict_integrity_inputs())
    )
    receipt["classification"] = "trajectory_audit_incomplete"
    receipt["integrity_qualified"] = False
    receipt["integrity_countable"] = False
    receipt["score_claim_eligible"] = False
    receipt["blockers"] = [blocker]

    with pytest.raises(ValueError, match="blockers_state_inconsistent"):
        normalize_benchmark_integrity_qualification_v1(receipt)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("invalid_step_count", 2, "invalid_step_count_inconsistent"),
        (
            "invalid_tool_calls_field_count",
            2,
            "invalid_tool_calls_field_count_inconsistent",
        ),
        ("observation_count", 2, "observation_count_inconsistent"),
    ],
)
def test_strict_integrity_normalizer_rejects_impossible_structural_counts(
    field: str, value: int, error: str
) -> None:
    receipt = copy.deepcopy(
        build_strict_benchmark_integrity_qualification(**_strict_integrity_inputs())
    )
    receipt["audit_coverage"][field] = value

    with pytest.raises(ValueError, match=error):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_normalizer_rejects_qualified_with_credential_evidence() -> (
    None
):
    receipt = copy.deepcopy(
        build_strict_benchmark_integrity_qualification(**_strict_integrity_inputs())
    )
    receipt["evidence_counts"]["credential_probe"] = 1
    receipt["evidence"] = [
        {
            "step_id": "step-1",
            "tool": "exec_command",
            "category": "credential_probe",
            "content_sha256": "a" * 64,
        }
    ]

    with pytest.raises(ValueError, match="blockers_state_inconsistent"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_normalizer_rejects_credential_evidence_forged_qualified() -> (
    None
):
    receipt = _strict_receipt_with_credential_probe()
    assert receipt["classification"] == "integrity_policy_violation"
    assert receipt["blockers"] == ["credential_probe"]
    receipt["classification"] = "integrity_qualified"
    receipt["integrity_qualified"] = True
    receipt["integrity_countable"] = True
    receipt["score_claim_eligible"] = True
    receipt["blockers"] = []

    with pytest.raises(ValueError, match="blockers_state_inconsistent"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_normalizer_rejects_wrong_failure_classification() -> None:
    receipt = _strict_receipt_with_credential_probe()
    receipt["classification"] = "runtime_isolation_not_attested"

    with pytest.raises(ValueError, match="classification_state_inconsistent"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_normalizer_rejects_restricted_review_category_mismatch() -> (
    None
):
    secret = "fixture-sensitive-value-123456"
    inputs = _strict_integrity_inputs()
    inputs["trajectory"] = {
        "schema_version": "ATIF-v1.7",
        "steps": [
            {
                "step_id": "step-1",
                "source": "agent",
                "tool_calls": [
                    {
                        "function_name": "exec_command",
                        "arguments": {"cmd": "cat /solution/solution.patch"},
                    }
                ],
                "observation": secret,
            }
        ],
    }
    inputs["trajectory_lineage_receipt"] = _trajectory_lineage(
        inputs["launch_admission_receipt"],
        inputs["trajectory"],
        inputs["external_agent_result"],
    )
    receipt = build_strict_benchmark_integrity_qualification(
        **inputs, sensitive_values=[secret]
    )
    receipt["restricted_access_review"]["suspected_categories"] = [
        "restricted_task_source_request"
    ]

    with pytest.raises(ValueError, match="suspected_categories_inconsistent"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_normalizer_rejects_bidirectional_cheating_mismatch() -> None:
    secret = "fixture-sensitive-value-123456"
    inputs = _strict_integrity_inputs()
    inputs["trajectory"] = {
        "schema_version": "ATIF-v1.7",
        "steps": [
            {
                "step_id": "step-1",
                "source": "agent",
                "tool_calls": [
                    {
                        "function_name": "exec_command",
                        "arguments": {"cmd": "cat /solution/solution.patch"},
                    }
                ],
                "observation": secret,
            }
        ],
    }
    inputs["trajectory_lineage_receipt"] = _trajectory_lineage(
        inputs["launch_admission_receipt"],
        inputs["trajectory"],
        inputs["external_agent_result"],
    )
    receipt = build_strict_benchmark_integrity_qualification(
        **inputs,
        sensitive_values=[secret],
        restricted_access_adjudication={
            "schema_version": "benchmark_restricted_access_adjudication_v0",
            "decision": "confirmed_cheating",
            "reviewer_role": "post_run_analyst",
            "reviewed_surfaces": [
                "solver_trajectory",
                "tool_results",
                "final_workspace",
            ],
            "restricted_material_disclosed": True,
            "causal_use_observed": True,
            "evidence_id": "review-1",
        },
    )
    receipt["benchmark_cheating_detected"] = False

    with pytest.raises(ValueError, match="cheating_state_inconsistent"):
        normalize_benchmark_integrity_qualification_v1(receipt)


def test_strict_integrity_matches_only_route_identity_case_insensitively() -> None:
    inputs = _strict_integrity_inputs()
    route = inputs["route_receipt"]
    route["requested_model"] = "gpt-5.4"
    route["requested_provider"] = "TRAE"
    route["observed_model"] = "GPT-5.4"
    route["observed_provider"] = "trae"

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["integrity_qualified"] is True
    assert receipt["launch_lineage"]["route_receipt_bound"] is True

    route["run_id"] = "RUN-1"
    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["integrity_qualified"] is False
    assert "route_receipt_run_id_mismatch" in receipt["blockers"]


@pytest.mark.parametrize(
    ("requested_field", "observed_field", "value"),
    (
        ("requested_model", "observed_model", "GPT-5.5"),
        ("requested_provider", "observed_provider", "other-provider"),
    ),
)
def test_strict_integrity_rejects_a_different_internally_verified_route(
    requested_field: str, observed_field: str, value: str
) -> None:
    inputs = _strict_integrity_inputs()
    route = inputs["route_receipt"]
    route[requested_field] = value
    route[observed_field] = value

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["integrity_qualified"] is False
    assert "route_receipt_requested_route_mismatch" in receipt["blockers"]


def test_strict_integrity_keeps_external_runner_role_separate_from_authority() -> None:
    launch = _launch(runner_authority="loopsbench")
    trajectory = _trajectory()
    result = _external_agent_result(launch)

    receipt = build_strict_benchmark_integrity_qualification(
        trajectory=trajectory,
        trajectory_lineage_receipt=_trajectory_lineage(launch, trajectory, result),
        external_agent_result=result,
        runtime_attestation=_attestation(launch),
        launch_admission_receipt=launch,
        route_receipt=_route(launch),
    )

    assert "containment_verification_authority" not in result["receipt"]
    assert receipt["launch_lineage"]["containment_absence_bound"] is True
    assert receipt["integrity_qualified"] is True
    assert receipt["launch_lineage"]["external_agent_result_bound"] is True
    assert receipt["launch_lineage"]["runtime_attestation_bound"] is True


def test_trajectory_lineage_normalizer_requires_containment_absence_proof() -> None:
    inputs = _strict_integrity_inputs()
    lineage = copy.deepcopy(inputs["trajectory_lineage_receipt"])
    lineage.pop("containment_absence_evidence_sha256")

    with pytest.raises(ValueError, match="trajectory_lineage_receipt_fields_invalid"):
        normalize_benchmark_trajectory_lineage_receipt(lineage)


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    [
        (
            "authority",
            "other-runner",
            "containment_absence_authority_mismatch",
        ),
        (
            "containment_binding_sha256",
            "0" * 64,
            "containment_absence_binding_sha256_mismatch",
        ),
        (
            "containment_termination_postcondition",
            "drained_before_result_consumption",
            "containment_absence_postcondition_mismatch",
        ),
        (
            "containment_absence_verified",
            False,
            "containment_absence_not_verified",
        ),
    ],
)
def test_strict_integrity_rejects_unbound_runner_containment_absence_proof(
    field: str, value: object, blocker: str
) -> None:
    inputs = _strict_integrity_inputs()
    inputs["trajectory_lineage_receipt"][field] = value

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["integrity_qualified"] is False
    assert receipt["classification"] == "launch_lineage_not_qualified"
    assert receipt["launch_lineage"]["containment_absence_bound"] is False
    assert blocker in receipt["blockers"]


@pytest.mark.parametrize(
    ("target", "field", "value", "blocker"),
    [
        (
            "result",
            "instruction_sha256",
            "0" * 64,
            "external_agent_result_instruction_sha256_mismatch",
        ),
        (
            "lineage",
            "run_id",
            "run-2",
            "trajectory_lineage_run_id_mismatch",
        ),
        (
            "lineage",
            "trajectory_sha256",
            "0" * 64,
            "trajectory_lineage_trajectory_sha256_mismatch",
        ),
        (
            "lineage",
            "external_agent_result_sha256",
            "0" * 64,
            "trajectory_lineage_external_agent_result_sha256_mismatch",
        ),
    ],
)
def test_strict_integrity_fails_closed_on_result_or_trajectory_lineage_mismatch(
    target: str, field: str, value: object, blocker: str
) -> None:
    inputs = _strict_integrity_inputs()
    if target == "result":
        inputs["external_agent_result"]["receipt"][field] = value
    else:
        inputs["trajectory_lineage_receipt"][field] = value

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["integrity_qualified"] is False
    assert receipt["classification"] == "launch_lineage_not_qualified"
    assert blocker in receipt["blockers"]


@pytest.mark.parametrize(
    ("target", "field", "value", "blocker"),
    [
        ("attestation", "run_id", "run-2", "runtime_attestation_run_id_mismatch"),
        ("attestation", "arm_id", "baseline", "runtime_attestation_arm_id_mismatch"),
        (
            "attestation",
            "runtime_binding_sha256",
            "f" * 64,
            "runtime_attestation_runtime_binding_sha256_mismatch",
        ),
        ("route", "run_id", "run-2", "route_receipt_run_id_mismatch"),
        ("route", "valid_mismatch", True, "route_receipt_runtime_verified_mismatch"),
    ],
)
def test_strict_integrity_fails_closed_on_runtime_or_route_lineage_mismatch(
    target: str, field: str, value: object, blocker: str
) -> None:
    inputs = _strict_integrity_inputs()
    launch = inputs["launch_admission_receipt"]
    if field == "valid_mismatch":
        inputs["route_receipt"] = build_traex_model_route_receipt(
            [
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "context": {
                            "model": "GPT-5.5",
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
    else:
        inputs["runtime_attestation" if target == "attestation" else "route_receipt"][
            field
        ] = value

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["integrity_qualified"] is False
    assert receipt["classification"] == "launch_lineage_not_qualified"
    assert blocker in receipt["blockers"]


@pytest.mark.parametrize(
    ("field", "private_value"),
    [
        ("benchmark_id", "private-tenant-benchmark-42"),
        ("case_id", "internal-suite/private-case-42"),
    ],
)
def test_strict_integrity_uses_admission_identifiers_in_failure_receipt(
    field: str, private_value: str
) -> None:
    inputs = _strict_integrity_inputs()
    launch = inputs["launch_admission_receipt"]
    inputs["runtime_attestation"][field] = private_value

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["integrity_qualified"] is False
    assert f"runtime_attestation_{field}_mismatch" in receipt["blockers"]
    assert receipt["benchmark_id"] == launch["benchmark_id"]
    assert receipt["case_id"] == launch["case_id"]
    assert private_value not in json.dumps(receipt, sort_keys=True)


def test_strict_integrity_rejects_policy_preimage_mismatch() -> None:
    receipt = build_strict_benchmark_integrity_qualification(
        **_strict_integrity_inputs(),
        policy={
            "schema_version": "benchmark_integrity_policy_v0",
            "policy_id": "different-policy",
            "network_access": "denied",
        },
    )

    assert receipt["integrity_qualified"] is False
    assert "integrity_policy_binding_mismatch" in receipt["blockers"]


def test_strict_integrity_requires_closed_bound_attestation_fields() -> None:
    inputs = _strict_integrity_inputs()
    inputs["runtime_attestation"]["unexpected"] = True

    with pytest.raises(ValueError, match="attestation_v1_fields_invalid"):
        build_strict_benchmark_integrity_qualification(**inputs)


def test_strict_integrity_classifies_false_runtime_attestation_as_typed_failure() -> (
    None
):
    inputs = _strict_integrity_inputs()
    inputs["runtime_attestation"]["agent_phase_isolated"] = False

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["classification"] == "runtime_isolation_not_attested"
    assert receipt["integrity_qualified"] is False
    assert "runtime_attestation_agent_phase_isolated_missing" in receipt["blockers"]
    assert receipt["runtime_attestation_checks"]["agent_phase_isolated"] is False


@pytest.mark.parametrize("value", [1, "false", None])
def test_strict_integrity_rejects_missing_or_non_boolean_runtime_attestation(
    value: object,
) -> None:
    inputs = _strict_integrity_inputs()
    if value is None:
        inputs["runtime_attestation"].pop("agent_phase_isolated")
    else:
        inputs["runtime_attestation"]["agent_phase_isolated"] = value

    with pytest.raises((TypeError, ValueError), match="attestation_v1_.*invalid"):
        build_strict_benchmark_integrity_qualification(**inputs)


@pytest.mark.parametrize(
    ("receipt_name", "field"),
    (
        ("launch_admission_receipt", "benchmark_id"),
        ("route_receipt", "runtime"),
    ),
)
def test_strict_integrity_rejects_declared_sensitive_receipt_identifiers(
    receipt_name: str, field: str
) -> None:
    secret = "fixture-private-identity-123456"
    inputs = _strict_integrity_inputs(
        benchmark_id=secret
        if receipt_name == "launch_admission_receipt"
        else "fixture@v0"
    )
    inputs[receipt_name][field] = secret

    with pytest.raises(ValueError) as error:
        build_strict_benchmark_integrity_qualification(
            **inputs, sensitive_values=(value for value in [secret])
        )

    assert secret not in str(error.value)


def test_strict_integrity_rejects_tampered_observed_route_state() -> None:
    inputs = _strict_integrity_inputs()
    inputs["route_receipt"]["observed_model"] = "GPT-5.5"

    with pytest.raises(ValueError, match="route_state_inconsistent"):
        build_strict_benchmark_integrity_qualification(**inputs)


def test_strict_integrity_rejects_open_trajectory_lineage_receipt() -> None:
    inputs = _strict_integrity_inputs()
    inputs["trajectory_lineage_receipt"]["unexpected"] = True

    with pytest.raises(ValueError, match="trajectory_lineage_receipt_fields_invalid"):
        build_strict_benchmark_integrity_qualification(**inputs)


def test_strict_integrity_rejects_non_terminal_external_agent_result() -> None:
    inputs = _strict_integrity_inputs()
    inputs["external_agent_result"]["receipt"]["classification"] = (
        "request_validated_not_executed"
    )

    with pytest.raises(ValueError, match="classification_invalid"):
        build_strict_benchmark_integrity_qualification(**inputs)


@pytest.mark.parametrize("startup", [False, True])
def test_strict_integrity_does_not_qualify_failed_terminal_result(
    startup: bool,
) -> None:
    inputs = _strict_integrity_inputs()
    launch = inputs["launch_admission_receipt"]
    failed_result = _failed_external_agent_result(launch, startup=startup)
    inputs["external_agent_result"] = failed_result
    inputs["trajectory_lineage_receipt"] = _trajectory_lineage(
        launch, inputs["trajectory"], failed_result
    )

    receipt = build_strict_benchmark_integrity_qualification(**inputs)

    assert receipt["integrity_qualified"] is False
    assert receipt["classification"] == "launch_lineage_not_qualified"
    assert "external_agent_result_solver_completed_mismatch" in receipt["blockers"]


def test_strict_integrity_requires_explicit_result_and_trajectory_lineage() -> None:
    inputs = _strict_integrity_inputs()
    inputs.pop("external_agent_result")
    inputs.pop("trajectory_lineage_receipt")

    with pytest.raises(ValueError, match="evidence_lineage_required"):
        build_strict_benchmark_integrity_qualification(**inputs)
