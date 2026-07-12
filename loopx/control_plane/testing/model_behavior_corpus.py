from __future__ import annotations

import copy
import random
from collections.abc import Iterable, Mapping
from typing import Any

from ..quota.turn_envelope import build_turn_envelope
from .model_behavior_qualification import (
    MODEL_BEHAVIOR_HARD_INVARIANT_FIELDS,
    MODEL_BEHAVIOR_SIGNAL_FIELDS,
    ModelBehaviorActor,
    ModelBehaviorPairValidationError,
    build_model_behavior_actor_request,
    run_model_behavior_qualification_pair,
)


MODEL_BEHAVIOR_CORPUS_SCHEMA_VERSION = "model_behavior_corpus_v0"
MODEL_BEHAVIOR_CORPUS_CASE_SCHEMA_VERSION = "model_behavior_corpus_case_v0"
MODEL_BEHAVIOR_CORPUS_RESULT_SCHEMA_VERSION = "model_behavior_corpus_result_v0"

_SOURCE_KINDS = {
    "state_matrix",
    "retained_public_decision",
    "counterfactual",
    "candidate_ablation",
}
_EXPECTED_OUTCOMES = {"equivalent", "fail_closed"}
_REQUIRED_UNGRADED_DIMENSIONS = (
    "concrete_user_question",
    "required_reads",
    "write_scope",
    "spend_rule",
    "scheduler_action",
    "vision_continuation",
    "actionable_warnings",
)


def _deep_merge(base: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(dict(base))
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _delete_path(payload: dict[str, Any], path: str) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ValueError("candidate ablation path must not be empty")
    cursor: dict[str, Any] = payload
    for part in parts[:-1]:
        value = cursor.get(part)
        if not isinstance(value, dict):
            raise ValueError(f"candidate ablation path does not exist: {path}")
        cursor = value
    if parts[-1] not in cursor:
        raise ValueError(f"candidate ablation path does not exist: {path}")
    del cursor[parts[-1]]


def _case(
    *,
    case_id: str,
    source_kind: str,
    full_packet: Mapping[str, Any],
    candidate_packet: Mapping[str, Any] | None = None,
    expected_outcome: str = "equivalent",
) -> dict[str, Any]:
    if not case_id or len(case_id) > 120:
        raise ValueError("corpus case_id must be a compact non-empty value")
    if source_kind not in _SOURCE_KINDS:
        raise ValueError("corpus source_kind is not supported")
    if expected_outcome not in _EXPECTED_OUTCOMES:
        raise ValueError("corpus expected_outcome is not supported")
    normalized_full = copy.deepcopy(dict(full_packet))
    build_model_behavior_actor_request(
        normalized_full,
        qualification_id=f"validate-{case_id}",
        arm="full_packet",
    )
    normalized_candidate = copy.deepcopy(
        dict(candidate_packet)
        if candidate_packet is not None
        else build_turn_envelope(normalized_full)
    )
    build_model_behavior_actor_request(
        normalized_candidate,
        qualification_id=f"validate-{case_id}",
        arm="candidate_packet",
    )
    return {
        "schema_version": MODEL_BEHAVIOR_CORPUS_CASE_SCHEMA_VERSION,
        "case_id": case_id,
        "source_kind": source_kind,
        "expected_outcome": expected_outcome,
        "full_packet": normalized_full,
        "candidate_packet": normalized_candidate,
    }


def build_model_behavior_corpus(
    base_packet: Mapping[str, Any],
    *,
    state_matrix: Mapping[str, Any] | None = None,
    retained_packets: Iterable[Mapping[str, Any]] = (),
    counterfactuals: Iterable[Mapping[str, Any]] = (),
    candidate_ablations: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build an in-memory corpus; callers must not persist its raw packets."""

    cases: list[dict[str, Any]] = []
    if state_matrix is not None:
        if state_matrix.get("schema_version") != "turn_envelope_state_matrix_v0":
            raise ValueError("state_matrix must use turn_envelope_state_matrix_v0")
        matrix_cases = state_matrix.get("cases")
        if not isinstance(matrix_cases, list):
            raise ValueError("state_matrix cases must be a list")
        for item in matrix_cases:
            if not isinstance(item, Mapping) or not isinstance(
                item.get("patch"), Mapping
            ):
                raise ValueError("state_matrix case must contain a patch object")
            name = str(item.get("name") or "")
            cases.append(
                _case(
                    case_id=f"matrix-{name}",
                    source_kind="state_matrix",
                    full_packet=_deep_merge(base_packet, item["patch"]),
                )
            )
    for item in retained_packets:
        packet = item.get("packet")
        if not isinstance(packet, Mapping):
            raise ValueError("retained packet entry must contain a packet object")
        cases.append(
            _case(
                case_id=str(item.get("case_id") or ""),
                source_kind="retained_public_decision",
                full_packet=packet,
            )
        )
    for item in counterfactuals:
        patch = item.get("patch")
        if not isinstance(patch, Mapping):
            raise ValueError("counterfactual entry must contain a patch object")
        cases.append(
            _case(
                case_id=str(item.get("case_id") or ""),
                source_kind="counterfactual",
                full_packet=_deep_merge(base_packet, patch),
            )
        )
    for item in candidate_ablations:
        path = str(item.get("path") or "")
        candidate = build_turn_envelope(base_packet)
        _delete_path(candidate, path)
        cases.append(
            _case(
                case_id=str(item.get("case_id") or ""),
                source_kind="candidate_ablation",
                full_packet=base_packet,
                candidate_packet=candidate,
                expected_outcome="fail_closed",
            )
        )
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("corpus case_id values must be unique")
    if not cases:
        raise ValueError("model behavior corpus must contain at least one case")
    return {
        "schema_version": MODEL_BEHAVIOR_CORPUS_SCHEMA_VERSION,
        "cases": cases,
        "persistence_boundary": {
            "raw_packets_persisted": False,
            "raw_model_responses_persisted": False,
            "raw_conversations_persisted": False,
        },
    }


def _compact_pair_result(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "evaluated",
        "equivalent": result.get("equivalent") is True,
        "actor_ref": result.get("actor_ref"),
        "hard_invariant_drift_fields": sorted(
            str(key) for key in dict(result.get("hard_invariant_drift") or {})
        ),
        "behavior_signal_drift_fields": sorted(
            str(key) for key in dict(result.get("behavior_signal_drift") or {})
        ),
        "stochastic_drift_fields": sorted(
            str(key) for key in dict(result.get("stochastic_drift") or {})
        ),
        "safety_violations": sorted(
            str(item) for item in list(result.get("safety_violations") or [])
        ),
        "receipt_digests": dict(result.get("receipt_digests") or {}),
    }


def run_model_behavior_corpus(
    corpus: Mapping[str, Any],
    *,
    actor: ModelBehaviorActor,
    repeats: int = 3,
    seed: int = 0,
) -> dict[str, Any]:
    if corpus.get("schema_version") != MODEL_BEHAVIOR_CORPUS_SCHEMA_VERSION:
        raise ValueError("corpus must use model_behavior_corpus_v0")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("corpus cases must be a non-empty list")
    if repeats < 2 or repeats > 20:
        raise ValueError("corpus repeats must be between 2 and 20")
    rng = random.Random(seed)
    case_results: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("corpus case must be an object")
        if case.get("schema_version") != MODEL_BEHAVIOR_CORPUS_CASE_SCHEMA_VERSION:
            raise ValueError("corpus case schema is not supported")
        expected = str(case.get("expected_outcome") or "")
        runs: list[dict[str, Any]] = []
        for repeat_index in range(repeats):
            arm_order = ["full_packet", "candidate_packet"]
            rng.shuffle(arm_order)
            try:
                result = run_model_behavior_qualification_pair(
                    case["full_packet"],
                    case["candidate_packet"],
                    qualification_id=f"{case['case_id']}-r{repeat_index + 1}",
                    actor=actor,
                    arm_order=(arm_order[0], arm_order[1]),
                )
                compact = _compact_pair_result(result)
            except ModelBehaviorPairValidationError:
                compact = {
                    "status": "fail_closed",
                    "equivalent": False,
                    "hard_invariant_drift_fields": [],
                    "behavior_signal_drift_fields": [],
                    "stochastic_drift_fields": [],
                    "safety_violations": ["pair_validation_failed"],
                    "receipt_digests": {},
                }
            compact.update(
                repeat_index=repeat_index + 1,
                arm_order=arm_order,
            )
            runs.append(compact)
        passed = all(
            (run["status"] == "evaluated" and run["equivalent"] is True)
            if expected == "equivalent"
            else run["status"] == "fail_closed"
            for run in runs
        )
        case_results.append(
            {
                "case_id": case["case_id"],
                "source_kind": case["source_kind"],
                "expected_outcome": expected,
                "passed": passed,
                "runs": runs,
            }
        )
    all_cases_passed = all(case["passed"] for case in case_results)
    return {
        "schema_version": MODEL_BEHAVIOR_CORPUS_RESULT_SCHEMA_VERSION,
        "seed": seed,
        "repeats": repeats,
        "case_count": len(case_results),
        "all_cases_passed": all_cases_passed,
        "promotion_eligible": all_cases_passed and not _REQUIRED_UNGRADED_DIMENSIONS,
        "coverage": {
            "graded_hard_invariants": list(MODEL_BEHAVIOR_HARD_INVARIANT_FIELDS),
            "graded_behavior_signals": list(MODEL_BEHAVIOR_SIGNAL_FIELDS),
            "ungraded_required_dimensions": list(_REQUIRED_UNGRADED_DIMENSIONS),
        },
        "cases": case_results,
        "persistence_boundary": {
            "raw_packets_persisted": False,
            "raw_model_responses_persisted": False,
            "raw_conversations_persisted": False,
        },
    }
