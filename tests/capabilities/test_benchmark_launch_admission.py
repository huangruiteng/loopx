from __future__ import annotations

import copy
import hashlib
import json

import pytest

from loopx.capabilities.benchmark_toolkit import (
    BENCHMARK_LAUNCH_ADMISSION_RECEIPT_SCHEMA_VERSION,
    benchmark_integrity_policy_sha256,
    build_benchmark_launch_admission_receipt,
    normalize_benchmark_integrity_policy,
    normalize_benchmark_launch_admission_receipt,
)
from loopx.capabilities.benchmark_toolkit.route_receipt import (
    PublicIdentityKind,
    public_identity_digest,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_launch_admission_matches_literal_interop_golden_fixture() -> None:
    instruction = "implement café"
    containment_receipt_ref = "fixture-containment:v1"
    expected = {
        "schema_version": "benchmark_launch_admission_receipt_v0",
        "benchmark_id": "loopsbench@v1",
        "case_id": "case-1",
        "run_id": "run-1",
        "arm_id": "loopx",
        "instruction_sha256": (
            "46bcafec03249f62c37f43cc29fb3e961c6981b833235063afec31cfd7d847e3"
        ),
        "integrity_policy_sha256": (
            "e1c2fc58882ccd74277a492d8fff431f88994820491e5fd3aea14e3ce60523c6"
        ),
        "expected_route": {"provider": "trae", "model": "GPT-5.4"},
        "containment_binding_sha256": (
            "01eef34cc4aef927ddd5a850bf503e6b37eec159020fbe47eecc192e166fec92"
        ),
        "runtime_binding_sha256": (
            "28b29f844329f6cc2493ef79ac3e2a6d1d75f7c8852de975ff418dd368a1b212"
        ),
        "credential_isolation": {
            "mechanism": "environment_exclusion",
            "authority": "loopsbench",
            "evidence_sha256": (
                "06e37d03b741559345a6a0a20e8f729388d4a56a16956b354e285e0e5e24984c"
            ),
        },
        "controller_isolation": {
            "mechanism": "container_boundary",
            "authority": "loopsbench",
            "evidence_sha256": (
                "a58248e3064a8bf056cc9a592f0c2ac981ab5c86b442180c5ccd9dea62edb3e2"
            ),
        },
        "runner_authority": "loopsbench",
        "provider_authority": "trae-adapter",
        "issued_at": "2026-09-03T00:30:00.000000Z",
        "launch_binding_digest": (
            "e5f7e98dbbd3eaef02393e3b35fed3783f5d736eddf63957ede32054d8f11d31"
        ),
        "public_boundary": {
            "raw_instruction_recorded": False,
            "raw_credential_recorded": False,
            "raw_controller_state_recorded": False,
            "raw_runtime_identity_recorded": False,
            "path_recorded": False,
        },
    }

    assert _sha(instruction) == expected["instruction_sha256"]
    assert _sha(containment_receipt_ref) == expected["containment_binding_sha256"]
    assert (
        build_benchmark_launch_admission_receipt(
            benchmark_id="loopsbench@v1",
            case_id="case-1",
            run_id="run-1",
            arm_id="loopx",
            instruction_sha256=(
                "46bcafec03249f62c37f43cc29fb3e961c6981b833235063afec31cfd7d847e3"
            ),
            integrity_policy_sha256=(
                "e1c2fc58882ccd74277a492d8fff431f88994820491e5fd3aea14e3ce60523c6"
            ),
            expected_provider="trae",
            expected_model="GPT-5.4",
            containment_binding_sha256=(
                "01eef34cc4aef927ddd5a850bf503e6b37eec159020fbe47eecc192e166fec92"
            ),
            runtime_binding_sha256=(
                "28b29f844329f6cc2493ef79ac3e2a6d1d75f7c8852de975ff418dd368a1b212"
            ),
            credential_isolation={
                "mechanism": "environment_exclusion",
                "authority": "loopsbench",
                "evidence_sha256": (
                    "06e37d03b741559345a6a0a20e8f729388d4a56a16956b354e285e0e5e24984c"
                ),
            },
            controller_isolation={
                "mechanism": "container_boundary",
                "authority": "loopsbench",
                "evidence_sha256": (
                    "a58248e3064a8bf056cc9a592f0c2ac981ab5c86b442180c5ccd9dea62edb3e2"
                ),
            },
            runner_authority="loopsbench",
            provider_authority="trae-adapter",
            issued_at="2026-09-03T00:30:00.000000Z",
        )
        == expected
    )


def _launch() -> dict[str, object]:
    return build_benchmark_launch_admission_receipt(
        benchmark_id="fixture@v0",
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
            "authority": "runner",
            "evidence_sha256": _sha("credential-evidence"),
        },
        controller_isolation={
            "mechanism": "container-namespace",
            "authority": "runner",
            "evidence_sha256": _sha("controller-evidence"),
        },
        runner_authority="runner",
        provider_authority="provider-adapter",
        issued_at="2026-09-03T08:30:00+08:00",
    )


def _replace_nested(
    value: dict[str, object], path: tuple[str, ...], replacement: object
) -> None:
    target = value
    for field in path[:-1]:
        nested = target[field]
        assert isinstance(nested, dict)
        target = nested
    target[path[-1]] = replacement


def test_launch_admission_is_canonical_public_safe_and_namespaced() -> None:
    launch = _launch()

    assert launch["schema_version"] == BENCHMARK_LAUNCH_ADMISSION_RECEIPT_SCHEMA_VERSION
    assert launch["case_id"] == "public-suite/case-1"
    assert launch["issued_at"] == "2026-09-03T00:30:00.000000Z"
    assert normalize_benchmark_launch_admission_receipt(launch) == launch
    rendered = json.dumps(launch, sort_keys=True)
    for private_value in (
        "container-7c9e",
        "/private/workspace",
        "sk-private-credential-value",
        "session-private-id",
    ):
        assert private_value not in rendered


def test_launch_admission_rejects_declared_sensitive_identity_and_route_labels() -> (
    None
):
    private_identity = "tenant-canary-42"
    for field in ("run_id", "expected_model", "provider_authority"):
        arguments = {
            "benchmark_id": "fixture@v0",
            "case_id": "case-1",
            "run_id": "run-1",
            "arm_id": "treatment",
            "instruction_sha256": _sha("instruction"),
            "integrity_policy_sha256": _sha("policy"),
            "expected_provider": "trae",
            "expected_model": "GPT-5.4",
            "containment_binding_sha256": _sha("containment"),
            "runtime_binding_sha256": _sha("runtime"),
            "credential_isolation": {
                "mechanism": "gateway",
                "authority": "runner",
                "evidence_sha256": _sha("credential"),
            },
            "controller_isolation": {
                "mechanism": "namespace",
                "authority": "runner",
                "evidence_sha256": _sha("controller"),
            },
            "runner_authority": "runner",
            "provider_authority": "provider-adapter",
            "issued_at": "2026-09-03T00:30:00Z",
            "sensitive_values": (private_identity,),
        }
        arguments[field] = private_identity

        with pytest.raises(ValueError, match=f"{field}_invalid"):
            build_benchmark_launch_admission_receipt(**arguments)


def test_launch_admission_accepts_typed_digest_for_private_identity() -> None:
    private_run_id = "tenant-canary-42"
    run_label = public_identity_digest(private_run_id, kind=PublicIdentityKind.RUN)
    launch = _launch()
    launch["run_id"] = run_label
    launch["launch_binding_digest"] = hashlib.sha256(
        json.dumps(
            {
                key: launch[key]
                for key in sorted(
                    set(launch) - {"launch_binding_digest", "public_boundary"}
                )
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    normalized = normalize_benchmark_launch_admission_receipt(
        launch, sensitive_values=(private_run_id,)
    )

    assert normalized["run_id"] == run_label
    assert private_run_id not in json.dumps(normalized)


@pytest.mark.parametrize(
    "case_id",
    [
        "/case-1",
        "suite/nested/case-1",
        "suite/../case-1",
        "suite\\case-1",
        "suite /case-1",
    ],
)
def test_launch_admission_rejects_path_like_case_ids(case_id: str) -> None:
    arguments = dict(
        benchmark_id="fixture@v0",
        case_id=case_id,
        run_id="run-1",
        arm_id="treatment",
        instruction_sha256=_sha("do the task"),
        integrity_policy_sha256=benchmark_integrity_policy_sha256(None),
        expected_provider="trae",
        expected_model="GPT-5.4",
        containment_binding_sha256=_sha("containment-ref"),
        runtime_binding_sha256=_sha("runtime-generation"),
        credential_isolation={
            "mechanism": "gateway",
            "authority": "wrong",
            "evidence_sha256": _sha("credential"),
        },
        controller_isolation={
            "mechanism": "namespace",
            "authority": "runner",
            "evidence_sha256": _sha("controller"),
        },
        runner_authority="runner",
        provider_authority="provider-adapter",
        issued_at="2026-09-03T00:30:00Z",
    )
    with pytest.raises(ValueError, match="case_id_invalid"):
        build_benchmark_launch_admission_receipt(**arguments)


@pytest.mark.parametrize(
    "field_path",
    [
        ("schema_version",),
        ("benchmark_id",),
        ("case_id",),
        ("run_id",),
        ("arm_id",),
        ("instruction_sha256",),
        ("integrity_policy_sha256",),
        ("expected_route", "provider"),
        ("expected_route", "model"),
        ("containment_binding_sha256",),
        ("runtime_binding_sha256",),
        ("credential_isolation", "mechanism"),
        ("credential_isolation", "authority"),
        ("credential_isolation", "evidence_sha256"),
        ("controller_isolation", "mechanism"),
        ("controller_isolation", "authority"),
        ("controller_isolation", "evidence_sha256"),
        ("runner_authority",),
        ("provider_authority",),
        ("issued_at",),
        ("launch_binding_digest",),
    ],
)
@pytest.mark.parametrize("non_string", [None, True, 7, [], {}])
def test_launch_admission_rejects_non_string_string_fields(
    field_path: tuple[str, ...], non_string: object
) -> None:
    launch = copy.deepcopy(_launch())
    _replace_nested(launch, field_path, non_string)

    with pytest.raises((TypeError, ValueError), match="invalid|unsupported"):
        normalize_benchmark_launch_admission_receipt(launch)


@pytest.mark.parametrize(
    "field_path",
    [
        ("benchmark_id",),
        ("case_id",),
        ("run_id",),
        ("arm_id",),
        ("expected_route", "provider"),
        ("expected_route", "model"),
        ("credential_isolation", "mechanism"),
        ("credential_isolation", "authority"),
        ("controller_isolation", "mechanism"),
        ("controller_isolation", "authority"),
        ("runner_authority",),
        ("provider_authority",),
    ],
)
def test_launch_admission_rejects_path_like_public_labels(
    field_path: tuple[str, ...],
) -> None:
    launch = copy.deepcopy(_launch())
    _replace_nested(launch, field_path, "/private/operator/value")

    with pytest.raises(ValueError, match="invalid"):
        normalize_benchmark_launch_admission_receipt(launch)


def test_launch_admission_normalizes_equivalent_timestamp_before_digest() -> None:
    first = _launch()
    second = _launch()
    second["issued_at"] = "2026-09-03T00:30:00Z"
    second["launch_binding_digest"] = first["launch_binding_digest"]

    assert normalize_benchmark_launch_admission_receipt(second) == first


def test_launch_admission_rejects_tampered_digest_and_mechanism_authority() -> None:
    launch = _launch()
    tampered = copy.deepcopy(launch)
    tampered["run_id"] = "run-2"
    with pytest.raises(ValueError, match="binding_digest_mismatch"):
        normalize_benchmark_launch_admission_receipt(tampered)

    with pytest.raises(ValueError, match="credential_isolation_authority_mismatch"):
        build_benchmark_launch_admission_receipt(
            benchmark_id="fixture@v0",
            case_id="case-1",
            run_id="run-1",
            arm_id="treatment",
            instruction_sha256=_sha("instruction"),
            integrity_policy_sha256=_sha("policy"),
            expected_provider="trae",
            expected_model="GPT-5.4",
            containment_binding_sha256=_sha("containment"),
            runtime_binding_sha256=_sha("runtime"),
            credential_isolation={
                "mechanism": "gateway",
                "authority": "wrong",
                "evidence_sha256": _sha("credential"),
            },
            controller_isolation={
                "mechanism": "namespace",
                "authority": "runner",
                "evidence_sha256": _sha("controller"),
            },
            runner_authority="runner",
            provider_authority="provider",
            issued_at="2026-09-03T00:30:00Z",
        )


def test_integrity_policy_digest_uses_normalized_effective_policy() -> None:
    implicit = normalize_benchmark_integrity_policy(None)
    explicit = normalize_benchmark_integrity_policy(
        {
            "schema_version": "benchmark_integrity_policy_v0",
            "policy_id": "default",
            "network_access": "denied",
        }
    )

    assert implicit == explicit
    assert benchmark_integrity_policy_sha256(None) == benchmark_integrity_policy_sha256(
        {
            "schema_version": "benchmark_integrity_policy_v0",
            "policy_id": "default",
            "network_access": "denied",
        }
    )
    assert implicit["denied_argument_markers"]["host_escape_probe"]
    with pytest.raises(ValueError, match="policy_fields_invalid"):
        normalize_benchmark_integrity_policy(
            {
                "schema_version": "benchmark_integrity_policy_v0",
                "policy_id": "default",
                "unexpected": True,
            }
        )
