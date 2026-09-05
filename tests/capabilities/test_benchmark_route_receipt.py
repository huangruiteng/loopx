from __future__ import annotations

import pytest

import loopx.capabilities.benchmark_toolkit as benchmark_toolkit
import loopx.capabilities.benchmark_toolkit.traex_evidence as traex_evidence
from loopx.capabilities.benchmark_toolkit.route_receipt import (
    BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION,
    PublicIdentityKind,
    normalize_benchmark_model_route_receipt_v1,
    public_identity_digest,
    route_identity_matches,
)


def test_provider_neutral_contract_is_reexported_by_public_and_traex_apis() -> None:
    assert (
        traex_evidence.BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
        == BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
    )
    assert (
        benchmark_toolkit.BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
        == BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION
    )
    assert (
        traex_evidence.normalize_benchmark_model_route_receipt_v1
        is normalize_benchmark_model_route_receipt_v1
    )
    assert (
        benchmark_toolkit.normalize_benchmark_model_route_receipt_v1
        is normalize_benchmark_model_route_receipt_v1
    )
    assert benchmark_toolkit.route_identity_matches is route_identity_matches


def _receipt(status: str, *, runtime: str = "codex") -> dict[str, object]:
    receipt: dict[str, object] = {
        "schema_version": BENCHMARK_MODEL_ROUTE_RECEIPT_V1_SCHEMA_VERSION,
        "runtime": runtime,
        "requested_model": "GPT-5.4",
        "requested_provider": "openai",
        "status": status,
        "raw_content_recorded": False,
        "input_path_recorded": False,
        "run_id": "run-1",
        "arm_id": "control",
        "launch_binding_digest": "a" * 64,
        "authority": "provider-adapter",
    }
    if status == "route_requested_not_runtime_audited":
        receipt.update(runtime_audited=False, matched=False, observed_route_count=0)
    elif status == "runtime_route_ambiguous":
        receipt.update(runtime_audited=True, matched=False, observed_route_count=2)
    elif status == "runtime_route_mismatch":
        receipt.update(
            runtime_audited=True,
            matched=False,
            observed_route_count=1,
            observed_model="GPT-5.5",
            observed_provider="openai",
        )
    elif status == "runtime_route_verified":
        receipt.update(
            runtime_audited=True,
            matched=True,
            observed_route_count=1,
            observed_model="gpt-5.4",
            observed_provider="OPENAI",
        )
    return receipt


@pytest.mark.parametrize(
    "status",
    (
        "route_requested_not_runtime_audited",
        "runtime_route_ambiguous",
        "runtime_route_mismatch",
        "runtime_route_verified",
    ),
)
def test_normalizer_accepts_provider_neutral_four_state_matrix(status: str) -> None:
    receipt = _receipt(status)

    assert normalize_benchmark_model_route_receipt_v1(receipt) == receipt


def test_normalizer_accepts_non_traex_runtime_and_mixed_case_verified_route() -> None:
    receipt = _receipt("runtime_route_verified", runtime="native-codex")

    normalized = normalize_benchmark_model_route_receipt_v1(receipt)

    assert normalized["runtime"] == "native-codex"
    assert normalized["observed_model"] == "gpt-5.4"
    assert normalized["observed_provider"] == "OPENAI"
    assert route_identity_matches(
        requested_model="GPT-5.4",
        requested_provider="openai",
        observed_model="gpt-5.4",
        observed_provider="OPENAI",
    )


def test_normalizer_accepts_one_complete_nonmatching_route() -> None:
    receipt = _receipt("runtime_route_mismatch")
    receipt["observed_model"] = "GPT-5.4"
    receipt["observed_provider"] = "other-provider"
    receipt["observed_backend_variant"] = "stable"

    assert normalize_benchmark_model_route_receipt_v1(receipt) == receipt


@pytest.mark.parametrize(
    ("status", "updates", "removed"),
    (
        (
            "route_requested_not_runtime_audited",
            {"observed_model": "GPT-5.4"},
            (),
        ),
        ("runtime_route_ambiguous", {"observed_route_count": 1}, ()),
        ("runtime_route_mismatch", {"observed_model": "gpt-5.4"}, ()),
        ("runtime_route_mismatch", {}, ("observed_provider",)),
        ("runtime_route_verified", {"observed_model": "GPT-5.5"}, ()),
        ("runtime_route_verified", {}, ("observed_model",)),
    ),
)
def test_normalizer_rejects_inconsistent_route_states(
    status: str, updates: dict[str, object], removed: tuple[str, ...]
) -> None:
    receipt = _receipt(status)
    receipt.update(updates)
    for field in removed:
        receipt.pop(field)

    with pytest.raises(ValueError, match="benchmark_model_route_state_inconsistent"):
        normalize_benchmark_model_route_receipt_v1(receipt)


def test_normalizer_rejects_unknown_fields() -> None:
    receipt = _receipt("runtime_route_verified")
    receipt["raw_runtime_payload"] = "must-not-cross-public-boundary"

    with pytest.raises(
        ValueError, match="benchmark_model_route_receipt_v1_fields_invalid"
    ):
        normalize_benchmark_model_route_receipt_v1(receipt)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("runtime", "runtime with spaces", "runtime must be"),
        ("requested_model", "/private/model", "requested_model must be"),
        ("launch_binding_digest", "A" * 64, "digest_invalid"),
        ("raw_content_recorded", True, "public_boundary_invalid"),
        ("input_path_recorded", True, "public_boundary_invalid"),
    ),
)
def test_normalizer_rejects_invalid_tokens_digest_and_public_boundary(
    field: str, value: object, error: str
) -> None:
    receipt = _receipt("runtime_route_verified")
    receipt[field] = value

    with pytest.raises(ValueError, match=error):
        normalize_benchmark_model_route_receipt_v1(receipt)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "runtime",
        "requested_model",
        "requested_provider",
        "status",
        "run_id",
        "arm_id",
        "launch_binding_digest",
        "authority",
        "observed_model",
        "observed_provider",
        "observed_backend_variant",
    ],
)
@pytest.mark.parametrize("non_string", [None, True, 7, [], {}])
def test_normalizer_rejects_non_string_string_fields(
    field: str, non_string: object
) -> None:
    receipt = _receipt("runtime_route_verified")
    receipt[field] = non_string

    with pytest.raises((TypeError, ValueError), match="invalid|must be"):
        normalize_benchmark_model_route_receipt_v1(receipt)


@pytest.mark.parametrize(
    "field",
    [
        "runtime",
        "requested_model",
        "requested_provider",
        "run_id",
        "arm_id",
        "authority",
        "observed_model",
        "observed_provider",
        "observed_backend_variant",
    ],
)
def test_normalizer_rejects_path_like_public_labels(field: str) -> None:
    receipt = _receipt("runtime_route_verified")
    receipt[field] = "/private/operator/value"

    with pytest.raises(ValueError, match="must be"):
        normalize_benchmark_model_route_receipt_v1(receipt)


@pytest.mark.parametrize(
    "field",
    ("runtime", "requested_model", "requested_provider", "observed_model"),
)
def test_route_receipt_rejects_declared_sensitive_auditable_labels(
    field: str,
) -> None:
    receipt = _receipt("runtime_route_verified")
    private_label = "private-route-canary"
    receipt[field] = private_label

    with pytest.raises(ValueError, match="declared sensitive value"):
        normalize_benchmark_model_route_receipt_v1(
            receipt, sensitive_values=(private_label,)
        )


def test_route_receipt_accepts_typed_opaque_run_id_and_rejects_wrong_kind() -> None:
    private_run_id = "private-run-identity"
    receipt = _receipt("runtime_route_verified")
    receipt["run_id"] = public_identity_digest(
        private_run_id, kind=PublicIdentityKind.RUN
    )

    normalized = normalize_benchmark_model_route_receipt_v1(
        receipt, sensitive_values=(private_run_id,)
    )

    assert normalized["run_id"].startswith("public:run:sha256:")
    receipt["run_id"] = public_identity_digest(
        private_run_id, kind=PublicIdentityKind.AUTHORITY
    )
    with pytest.raises(ValueError, match="digest kind is invalid"):
        normalize_benchmark_model_route_receipt_v1(receipt)


def test_route_receipt_does_not_silently_hash_provider_or_model_labels() -> None:
    receipt = _receipt("runtime_route_verified")
    receipt["requested_model"] = public_identity_digest(
        "private-model", kind=PublicIdentityKind.RUN
    )

    with pytest.raises(ValueError, match="explicit public route label"):
        normalize_benchmark_model_route_receipt_v1(receipt)
