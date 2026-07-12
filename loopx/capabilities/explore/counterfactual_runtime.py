"""Failure-driven counterfactual suffix replay for Explore Episode V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from .replay_runtime import (
    ReplayChildExecutionContext,
    ReplayChildExecutionFailure,
    ReplayChildExecutionResult,
    ReplayChildTask,
    ReplayFidelity,
    ReplayPoint,
    ReplayPointRegistry,
    ReplayRestoreResult,
)
from .trace_runtime import TraceLog, freeze_public_mapping


def _required_text(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


class CounterfactualDecision(str, Enum):
    PROMOTED = "promoted"
    REJECTED = "rejected"
    OBSERVED_ONLY = "observed_only"


@dataclass(frozen=True)
class ValidationTarget:
    validation_id: str
    baseline_passed: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "validation_id",
            _required_text(self.validation_id, "validation_id"),
        )
        object.__setattr__(self, "baseline_passed", bool(self.baseline_passed))


@dataclass(frozen=True)
class ValidationOutcome:
    validation_id: str
    passed: bool
    public_summary: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "validation_id",
            _required_text(self.validation_id, "validation_id"),
        )
        object.__setattr__(self, "passed", bool(self.passed))
        if self.public_summary is not None:
            frozen = freeze_public_mapping(
                {"public_summary": self.public_summary},
                field_path="validation_outcome",
            )
            object.__setattr__(
                self,
                "public_summary",
                frozen["public_summary"],
            )


@dataclass(frozen=True)
class CounterfactualHypothesis:
    hypothesis_id: str
    first_affected_event_id: str
    first_affected_sequence: int
    fix_set: tuple[ValidationTarget, ...]
    guard_set: tuple[ValidationTarget, ...]
    minimum_fidelity: ReplayFidelity = ReplayFidelity.SEMANTIC_EQUIVALENT

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "hypothesis_id",
            _required_text(self.hypothesis_id, "hypothesis_id"),
        )
        object.__setattr__(
            self,
            "first_affected_event_id",
            _required_text(self.first_affected_event_id, "first_affected_event_id"),
        )
        if int(self.first_affected_sequence) < 0:
            raise ValueError("first_affected_sequence must be non-negative")
        object.__setattr__(
            self,
            "first_affected_sequence",
            int(self.first_affected_sequence),
        )
        fix_set = tuple(self.fix_set)
        guard_set = tuple(self.guard_set)
        if not fix_set:
            raise ValueError("fix_set must contain at least one failed baseline target")
        if not guard_set:
            raise ValueError(
                "guard_set must contain at least one passing baseline target"
            )
        if not all(
            isinstance(target, ValidationTarget) for target in (*fix_set, *guard_set)
        ):
            raise TypeError(
                "fix_set and guard_set must contain ValidationTarget values"
            )
        if any(target.baseline_passed for target in fix_set):
            raise ValueError("fix_set targets must fail in the baseline")
        if any(not target.baseline_passed for target in guard_set):
            raise ValueError("guard_set targets must pass in the baseline")
        ids = [target.validation_id for target in (*fix_set, *guard_set)]
        if len(ids) != len(set(ids)):
            raise ValueError("fix_set and guard_set validation ids must be unique")
        object.__setattr__(self, "fix_set", fix_set)
        object.__setattr__(self, "guard_set", guard_set)
        object.__setattr__(
            self,
            "minimum_fidelity",
            ReplayFidelity(self.minimum_fidelity),
        )
        if self.minimum_fidelity == ReplayFidelity.NON_REPLAYABLE:
            raise ValueError("counterfactual replay requires a replayable fidelity")


@dataclass(frozen=True)
class CounterfactualCandidate:
    candidate_id: str
    public_change_set: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            _required_text(self.candidate_id, "candidate_id"),
        )
        object.__setattr__(
            self,
            "public_change_set",
            freeze_public_mapping(
                self.public_change_set,
                field_path="public_change_set",
            ),
        )


@dataclass(frozen=True)
class CounterfactualReplayRequest:
    hypothesis_id: str
    candidate_id: str
    replay_point: ReplayPoint
    first_affected_event_id: str
    first_affected_sequence: int
    public_change_set: Mapping[str, Any]


@dataclass(frozen=True)
class CounterfactualChildCandidate:
    candidate: CounterfactualCandidate
    target_branch_id: str
    execute_suffix: Callable[
        [ReplayChildExecutionContext, CounterfactualReplayRequest],
        Mapping[str, bool | ValidationOutcome],
    ] = field(repr=False, compare=False)
    intent: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, CounterfactualCandidate):
            raise TypeError("candidate must be a CounterfactualCandidate")
        object.__setattr__(
            self,
            "target_branch_id",
            _required_text(self.target_branch_id, "target_branch_id"),
        )
        if not callable(self.execute_suffix):
            raise TypeError("execute_suffix must be callable")
        object.__setattr__(
            self,
            "intent",
            freeze_public_mapping(
                self.intent, field_path="counterfactual_child_intent"
            ),
        )


@dataclass(frozen=True)
class CounterfactualReplayResult:
    hypothesis_id: str
    candidate_id: str
    replay_point_id: str
    restore: ReplayRestoreResult
    decision: CounterfactualDecision
    outcomes: tuple[ValidationOutcome, ...]
    missing_validations: tuple[str, ...]
    failed_fixes: tuple[str, ...]
    regressed_guards: tuple[str, ...]
    addressed_prefix_event_count: int
    avoided_prefix_event_count: int
    verified_reused_prefix_event_count: int
    replay_distance_events: int
    reason: str

    @property
    def promoted(self) -> bool:
        return self.decision == CounterfactualDecision.PROMOTED

    def to_record(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "candidate_id": self.candidate_id,
            "replay_point_id": self.replay_point_id,
            "restore": self.restore.to_record(),
            "decision": self.decision.value,
            "outcomes": [
                {
                    "validation_id": outcome.validation_id,
                    "passed": outcome.passed,
                    "public_summary": outcome.public_summary,
                }
                for outcome in self.outcomes
            ],
            "missing_validations": list(self.missing_validations),
            "failed_fixes": list(self.failed_fixes),
            "regressed_guards": list(self.regressed_guards),
            "addressed_prefix_event_count": self.addressed_prefix_event_count,
            "avoided_prefix_event_count": self.avoided_prefix_event_count,
            "verified_reused_prefix_event_count": (
                self.verified_reused_prefix_event_count
            ),
            "replay_distance_events": self.replay_distance_events,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CounterfactualChildCandidateResult:
    candidate_id: str
    replay_result: CounterfactualReplayResult | None = None
    execution_result: ReplayChildExecutionResult | None = None
    execution_failure: ReplayChildExecutionFailure | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            _required_text(self.candidate_id, "candidate_id"),
        )
        if (self.replay_result is None) == (self.execution_failure is None):
            raise ValueError(
                "exactly one replay_result or execution_failure is required"
            )
        if (self.replay_result is None) != (self.execution_result is None):
            raise ValueError(
                "replay_result and execution_result must be present together"
            )

    @property
    def evaluated(self) -> bool:
        return self.replay_result is not None

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": "evaluated" if self.evaluated else "execution_failed",
            "replay_result": (
                self.replay_result.to_record()
                if self.replay_result is not None
                else None
            ),
            "execution_result": (
                self.execution_result.to_record()
                if self.execution_result is not None
                else None
            ),
            "execution_failure": (
                self.execution_failure.to_record()
                if self.execution_failure is not None
                else None
            ),
        }


@dataclass(frozen=True)
class CounterfactualChildGroupResult:
    hypothesis_id: str
    replay_point_id: str
    candidates: tuple[CounterfactualChildCandidateResult, ...]
    parallel_requested: bool

    def to_record(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "replay_point_id": self.replay_point_id,
            "parallel_requested": self.parallel_requested,
            "candidate_count": len(self.candidates),
            "evaluated_count": sum(
                candidate.evaluated for candidate in self.candidates
            ),
            "execution_failure_count": sum(
                not candidate.evaluated for candidate in self.candidates
            ),
            "candidates": [candidate.to_record() for candidate in self.candidates],
        }


def _normalize_validation_outcomes(
    raw_outcomes: Mapping[str, bool | ValidationOutcome],
) -> tuple[ValidationOutcome, ...]:
    if not isinstance(raw_outcomes, Mapping):
        raise TypeError(
            "counterfactual suffix execution must return a validation mapping"
        )
    outcomes: list[ValidationOutcome] = []
    for raw_id, raw_outcome in raw_outcomes.items():
        validation_id = _required_text(str(raw_id), "validation_id")
        if isinstance(raw_outcome, ValidationOutcome):
            if raw_outcome.validation_id != validation_id:
                raise ValueError("validation outcome key must match its validation_id")
            outcome = raw_outcome
        elif isinstance(raw_outcome, bool):
            outcome = ValidationOutcome(validation_id=validation_id, passed=raw_outcome)
        else:
            raise TypeError(
                "validation outcomes must be bool or ValidationOutcome values"
            )
        outcomes.append(outcome)
    return tuple(outcomes)


def evaluate_counterfactual_candidate(
    *,
    trace: TraceLog,
    hypothesis: CounterfactualHypothesis,
    candidate: CounterfactualCandidate,
    replay_point: ReplayPoint,
    restore: ReplayRestoreResult,
    raw_outcomes: Mapping[str, bool | ValidationOutcome],
) -> CounterfactualReplayResult:
    """Apply fix/guard promotion to an already executed replay candidate.

    This is the composition seam for isolated child execution: child runtimes
    own restore and risk interception, then hand their public validation
    outcomes to the same promotion contract used by serial replay.
    """

    affected_event = trace.event(hypothesis.first_affected_event_id)
    if affected_event.sequence != hypothesis.first_affected_sequence:
        raise ValueError(
            "first affected event sequence does not match the addressable trace"
        )
    if replay_point.cursor.trace_id != trace.trace_id:
        raise ValueError("ReplayPoint trace does not match the hypothesis trace")
    if replay_point.cursor.branch_id != trace.branch_id:
        raise ValueError("ReplayPoint branch does not match the hypothesis trace")
    if replay_point.cursor.next_sequence > hypothesis.first_affected_sequence:
        raise ValueError("ReplayPoint must precede the first affected event")
    if restore.replay_point_id != replay_point.replay_point_id:
        raise ValueError("restore result does not belong to the ReplayPoint")

    outcomes = _normalize_validation_outcomes(raw_outcomes)
    by_id = {outcome.validation_id: outcome for outcome in outcomes}
    required_ids = [
        target.validation_id for target in (*hypothesis.fix_set, *hypothesis.guard_set)
    ]
    missing = tuple(
        validation_id for validation_id in required_ids if validation_id not in by_id
    )
    failed_fixes = tuple(
        target.validation_id
        for target in hypothesis.fix_set
        if target.validation_id in by_id and not by_id[target.validation_id].passed
    )
    regressed_guards = tuple(
        target.validation_id
        for target in hypothesis.guard_set
        if target.validation_id in by_id and not by_id[target.validation_id].passed
    )

    if not restore.promotion_eligible:
        decision = CounterfactualDecision.OBSERVED_ONLY
        reason = "restore fidelity or equivalence is insufficient for promotion"
    elif missing:
        decision = CounterfactualDecision.REJECTED
        reason = "required validation outcomes are missing"
    elif failed_fixes:
        decision = CounterfactualDecision.REJECTED
        reason = "one or more fix targets remain failing"
    elif regressed_guards:
        decision = CounterfactualDecision.REJECTED
        reason = "one or more guard targets regressed"
    else:
        decision = CounterfactualDecision.PROMOTED
        reason = "all fix targets passed and no guard target regressed"

    addressed_prefix_event_count = replay_point.cursor.next_sequence
    return CounterfactualReplayResult(
        hypothesis_id=hypothesis.hypothesis_id,
        candidate_id=candidate.candidate_id,
        replay_point_id=replay_point.replay_point_id,
        restore=restore,
        decision=decision,
        outcomes=outcomes,
        missing_validations=missing,
        failed_fixes=failed_fixes,
        regressed_guards=regressed_guards,
        addressed_prefix_event_count=addressed_prefix_event_count,
        # Compatibility field: V2 initially called logical addressing
        # "avoidance" before live Adapters could report physical reuse.
        avoided_prefix_event_count=addressed_prefix_event_count,
        verified_reused_prefix_event_count=(
            addressed_prefix_event_count if restore.prefix_reused is True else 0
        ),
        replay_distance_events=max(
            0,
            hypothesis.first_affected_sequence - replay_point.cursor.next_sequence,
        ),
        reason=reason,
    )


def run_counterfactual_child_group(
    registry: ReplayPointRegistry,
    *,
    trace: TraceLog,
    hypothesis: CounterfactualHypothesis,
    candidates: Sequence[CounterfactualChildCandidate],
    parallel: bool = False,
    max_workers: int | None = None,
) -> CounterfactualChildGroupResult:
    """Execute and evaluate isolated counterfactual candidates in one group."""

    normalized_candidates = tuple(candidates)
    if not normalized_candidates:
        raise ValueError("counterfactual child group requires at least one candidate")
    if not all(
        isinstance(candidate, CounterfactualChildCandidate)
        for candidate in normalized_candidates
    ):
        raise TypeError("candidates must contain CounterfactualChildCandidate values")
    affected_event = trace.event(hypothesis.first_affected_event_id)
    if affected_event.sequence != hypothesis.first_affected_sequence:
        raise ValueError(
            "first affected event sequence does not match the addressable trace"
        )
    point = registry.select_before(
        trace_id=trace.trace_id,
        branch_id=trace.branch_id,
        first_affected_sequence=hypothesis.first_affected_sequence,
        minimum_fidelity=hypothesis.minimum_fidelity,
    )

    def task_for(spec: CounterfactualChildCandidate) -> ReplayChildTask:
        request = CounterfactualReplayRequest(
            hypothesis_id=hypothesis.hypothesis_id,
            candidate_id=spec.candidate.candidate_id,
            replay_point=point,
            first_affected_event_id=hypothesis.first_affected_event_id,
            first_affected_sequence=hypothesis.first_affected_sequence,
            public_change_set=spec.candidate.public_change_set,
        )

        def execute(context: ReplayChildExecutionContext):
            return spec.execute_suffix(context, request)

        return ReplayChildTask(
            child_id=spec.candidate.candidate_id,
            target_branch_id=spec.target_branch_id,
            minimum_fidelity=hypothesis.minimum_fidelity,
            execute=execute,
            intent=spec.intent,
        )

    settled = registry.run_child_group_settled_from(
        point.replay_point_id,
        tuple(task_for(candidate) for candidate in normalized_candidates),
        parallel=parallel,
        max_workers=max_workers,
    )
    specs_by_id = {
        candidate.candidate.candidate_id: candidate
        for candidate in normalized_candidates
    }
    results: list[CounterfactualChildCandidateResult] = []
    for child_result in settled:
        spec = specs_by_id[child_result.child_id]
        if isinstance(child_result, ReplayChildExecutionFailure):
            results.append(
                CounterfactualChildCandidateResult(
                    candidate_id=child_result.child_id,
                    execution_failure=child_result,
                )
            )
            continue
        if not isinstance(child_result, ReplayChildExecutionResult):
            raise TypeError("unexpected settled child result type")
        results.append(
            CounterfactualChildCandidateResult(
                candidate_id=child_result.child_id,
                execution_result=child_result,
                replay_result=evaluate_counterfactual_candidate(
                    trace=trace,
                    hypothesis=hypothesis,
                    candidate=spec.candidate,
                    replay_point=point,
                    restore=child_result.restore,
                    raw_outcomes=child_result.outcome,
                ),
            )
        )
    return CounterfactualChildGroupResult(
        hypothesis_id=hypothesis.hypothesis_id,
        replay_point_id=point.replay_point_id,
        candidates=tuple(results),
        parallel_requested=bool(parallel),
    )


def run_counterfactual_suffix_replay(
    registry: ReplayPointRegistry,
    *,
    trace: TraceLog,
    hypothesis: CounterfactualHypothesis,
    candidate: CounterfactualCandidate,
    execute_suffix: Callable[
        [CounterfactualReplayRequest],
        Mapping[str, bool | ValidationOutcome],
    ],
) -> CounterfactualReplayResult:
    """Replay one changed suffix and apply the first V2 promotion contract."""

    affected_event = trace.event(hypothesis.first_affected_event_id)
    if affected_event.sequence != hypothesis.first_affected_sequence:
        raise ValueError(
            "first affected event sequence does not match the addressable trace"
        )

    point = registry.select_before(
        trace_id=trace.trace_id,
        branch_id=trace.branch_id,
        first_affected_sequence=hypothesis.first_affected_sequence,
        minimum_fidelity=hypothesis.minimum_fidelity,
    )
    request = CounterfactualReplayRequest(
        hypothesis_id=hypothesis.hypothesis_id,
        candidate_id=candidate.candidate_id,
        replay_point=point,
        first_affected_event_id=hypothesis.first_affected_event_id,
        first_affected_sequence=hypothesis.first_affected_sequence,
        public_change_set=candidate.public_change_set,
    )

    def execute(
        restore: ReplayRestoreResult,
    ) -> Mapping[str, bool | ValidationOutcome]:
        del restore
        return execute_suffix(request)

    restore, raw_outcomes = registry.run_from(
        point.replay_point_id,
        target_branch_id=f"counterfactual-{candidate.candidate_id}",
        minimum_fidelity=hypothesis.minimum_fidelity,
        execute=execute,
    )
    return evaluate_counterfactual_candidate(
        trace=trace,
        hypothesis=hypothesis,
        candidate=candidate,
        replay_point=point,
        restore=restore,
        raw_outcomes=raw_outcomes,
    )
