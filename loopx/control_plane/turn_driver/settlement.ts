import {
  commitStepPayload,
  isCommittedPayload,
  requireMatchingEffectId,
  seedCommittedSteps,
  settlementFailed,
  settlementIdentityFromPlan,
  settlementNextAction,
  settlementPure,
  settlementResultPayload,
  type JsonObject,
  type SettlementFailureResult,
  type SettlementIdentity,
  type SettlementResult,
  type SettlementStepKind,
} from "../effect_program.ts";
import {
  optionalNonEmptyString,
  requireBoolean,
  requireJsonObject,
  requireNonEmptyString,
  requireStringArray,
  requireStringLiteral,
} from "../runtime_decode.ts";

export const TURN_SETTLEMENT_TRANSACTION_SCHEMA_VERSION =
  "loopx_turn_settlement_transaction_v0";
export const TURN_SETTLEMENT_REDUCTION_SCHEMA_VERSION =
  "loopx_turn_settlement_reduction_v0";

const BASE_SETTLEMENT_STEPS = [
  "validation",
  "durable_writeback",
  "quota_spend",
] as const satisfies readonly SettlementStepKind[];

const PROVIDER_STEP_KINDS = [
  "durable_writeback",
  "quota_spend",
  "terminal_closeout",
] as const;
type ProviderStepKind = (typeof PROVIDER_STEP_KINDS)[number];

const PROVIDER_RESOLUTION_KINDS = ["committed", "absent", "unknown"] as const;
type ProviderResolutionKind = (typeof PROVIDER_RESOLUTION_KINDS)[number];

interface PreparedEffectAttempt {
  status: "prepared";
  effect_ref: string;
}

interface ProviderObservation {
  kind: ProviderResolutionKind;
  payload: JsonObject | null;
  reason: string | null;
}

interface FailedProviderAttempt {
  step_kind: ProviderStepKind;
  payload: JsonObject;
}

interface ProviderExecutionEffect {
  step_kind: ProviderStepKind;
  action: "prepare_and_execute";
  effect_ref: string;
  completed_phases: readonly string[];
}

interface ProviderResolutionEffect {
  step_kind: ProviderStepKind;
  action: "resolve_prepared";
  effect_ref: string;
  completed_phases: readonly string[];
  resolution_policy: {
    committed: "checkpoint";
    absent: "execute";
    unknown: "fail_closed";
  };
}

type ProviderEffect = ProviderExecutionEffect | ProviderResolutionEffect;

interface TurnSettlementRequest {
  schema_version: typeof TURN_SETTLEMENT_TRANSACTION_SCHEMA_VERSION;
  transaction_plan: JsonObject;
  transaction_phases: readonly string[];
  completed_phases: readonly string[];
  committed_effect_id: string | null;
  writeback_payload: JsonObject | null;
  quota_spend_payload: JsonObject | null;
  terminal_closeout_required: boolean;
  terminal_closeout_payload: JsonObject | null;
  failed_provider_attempt: FailedProviderAttempt | null;
  effect_attempts: Partial<Record<ProviderStepKind, PreparedEffectAttempt>>;
  provider_observations: Partial<Record<ProviderStepKind, ProviderObservation>>;
}

export interface TurnSettlementState {
  completed_phases: readonly string[];
  writeback: JsonObject | null;
  quota_spend: JsonObject | null;
}

interface TurnSettlementExecution {
  schema_version: typeof TURN_SETTLEMENT_REDUCTION_SCHEMA_VERSION;
  decision: "execute";
  provider_effects: readonly ProviderEffect[];
  result: null;
  settlement_result: null;
}

interface TurnSettlementOutcome {
  schema_version: typeof TURN_SETTLEMENT_REDUCTION_SCHEMA_VERSION;
  decision: "complete" | "failed";
  provider_effects: readonly [];
  result: SettlementResult<TurnSettlementState>;
  settlement_result: JsonObject;
}

export type TurnSettlementReduction =
  | TurnSettlementExecution
  | TurnSettlementOutcome;

function optionalObject(value: unknown, label: string): JsonObject | null {
  if (value === null || value === undefined) return null;
  return requireJsonObject(value, label);
}

function decodeFailedProviderAttempt(
  value: unknown,
): FailedProviderAttempt | null {
  if (value === null || value === undefined) return null;
  const attempt = requireJsonObject(value, "failed_provider_attempt");
  return {
    step_kind: requireStringLiteral(
      attempt.step_kind,
      PROVIDER_STEP_KINDS,
      "failed_provider_attempt.step_kind",
    ),
    payload: requireJsonObject(
      attempt.payload,
      "failed_provider_attempt.payload",
    ),
  };
}

function decodeProviderRecord<Value>(
  value: unknown,
  label: string,
  decode: (value: unknown, label: string) => Value,
): Partial<Record<ProviderStepKind, Value>> {
  if (value === null || value === undefined) return {};
  const record = requireJsonObject(value, label);
  const decoded: Partial<Record<ProviderStepKind, Value>> = {};
  for (const [rawStep, rawValue] of Object.entries(record)) {
    const step = requireStringLiteral(
      rawStep,
      PROVIDER_STEP_KINDS,
      `${label} step`,
    );
    decoded[step] = decode(rawValue, `${label}.${step}`);
  }
  return decoded;
}

function decodePreparedAttempt(
  value: unknown,
  label: string,
): PreparedEffectAttempt {
  const attempt = requireJsonObject(value, label);
  return {
    status: requireStringLiteral(
      attempt.status,
      ["prepared"] as const,
      `${label}.status`,
    ),
    effect_ref: requireNonEmptyString(attempt.effect_ref, `${label}.effect_ref`),
  };
}

function decodeProviderObservation(
  value: unknown,
  label: string,
): ProviderObservation {
  const observation = requireJsonObject(value, label);
  return {
    kind: requireStringLiteral(
      observation.kind,
      PROVIDER_RESOLUTION_KINDS,
      `${label}.kind`,
    ),
    payload: optionalObject(observation.payload, `${label}.payload`),
    reason: optionalNonEmptyString(observation.reason, `${label}.reason`),
  };
}

function decodeRequest(value: unknown): TurnSettlementRequest {
  const request = requireJsonObject(value, "Turn settlement request");
  const schemaVersion = requireStringLiteral(
    request.schema_version,
    [TURN_SETTLEMENT_TRANSACTION_SCHEMA_VERSION] as const,
    "schema_version",
  );
  return {
    schema_version: schemaVersion,
    transaction_plan: requireJsonObject(
      request.transaction_plan,
      "transaction_plan",
    ),
    transaction_phases: requireStringArray(
      request.transaction_phases,
      "transaction_phases",
    ),
    completed_phases: requireStringArray(
      request.completed_phases,
      "completed_phases",
    ),
    committed_effect_id: optionalNonEmptyString(
      request.committed_effect_id,
      "committed_effect_id",
    ),
    writeback_payload: optionalObject(
      request.writeback_payload,
      "writeback_payload",
    ),
    quota_spend_payload: optionalObject(
      request.quota_spend_payload,
      "quota_spend_payload",
    ),
    terminal_closeout_required: requireBoolean(
      request.terminal_closeout_required,
      "terminal_closeout_required",
    ),
    terminal_closeout_payload: optionalObject(
      request.terminal_closeout_payload,
      "terminal_closeout_payload",
    ),
    failed_provider_attempt: decodeFailedProviderAttempt(
      request.failed_provider_attempt,
    ),
    effect_attempts: decodeProviderRecord(
      request.effect_attempts,
      "effect_attempts",
      decodePreparedAttempt,
    ),
    provider_observations: decodeProviderRecord(
      request.provider_observations,
      "provider_observations",
      decodeProviderObservation,
    ),
  };
}

function reduction(
  result: SettlementResult<TurnSettlementState>,
): TurnSettlementOutcome {
  return {
    schema_version: TURN_SETTLEMENT_REDUCTION_SCHEMA_VERSION,
    decision: result.failure === null ? "complete" : "failed",
    provider_effects: [],
    result,
    settlement_result: settlementResultPayload(result),
  };
}

function execution(
  providerEffects: readonly ProviderEffect[],
): TurnSettlementExecution {
  return {
    schema_version: TURN_SETTLEMENT_REDUCTION_SCHEMA_VERSION,
    decision: "execute",
    provider_effects: providerEffects,
    result: null,
    settlement_result: null,
  };
}

function failedState(
  failure: SettlementFailureResult,
): TurnSettlementOutcome {
  return reduction(failure);
}

function providerFailure(
  identity: SettlementIdentity,
  request: TurnSettlementRequest,
  stepKind: ProviderStepKind,
  receipts: SettlementResult<unknown>["receipts"],
): TurnSettlementOutcome {
  const attempt = request.failed_provider_attempt;
  if (!attempt || attempt.step_kind !== stepKind) {
    return reduction(
      settlementFailed({
        kind: "receipt_missing",
        step_kind: stepKind,
        reason: `Turn settlement is missing its ${stepKind} provider outcome`,
        receipts,
      }),
    );
  }
  const committed = commitStepPayload({
    identity,
    step_kind: stepKind,
    transaction_phases:
      stepKind === "terminal_closeout"
        ? ["terminal_closeout"]
        : request.transaction_phases,
    payload: attempt.payload,
  });
  if (committed.result.failure === null) {
    throw new Error(
      `failed_provider_attempt for ${stepKind} unexpectedly committed`,
    );
  }
  return reduction({
    value: null,
    receipts: [...receipts, ...committed.result.receipts],
    failure: committed.result.failure,
  });
}

function pendingProviderEffects(
  request: TurnSettlementRequest,
  identity: SettlementIdentity,
  firstStep: ProviderStepKind,
): readonly ProviderEffect[] {
  const completed = new Set(request.completed_phases);
  const effects: ProviderEffect[] = [];
  for (const step of BASE_SETTLEMENT_STEPS) {
    if (step === "validation" || completed.has(step)) continue;
    const phaseIndex = request.transaction_phases.indexOf(step);
    if (phaseIndex < 0) {
      throw new Error(`transaction phases do not contain ${step}`);
    }
    effects.push({
      step_kind: step,
      action: "prepare_and_execute",
      effect_ref: `${identity.effect_id}#${step}`,
      completed_phases: request.transaction_phases.slice(0, phaseIndex + 1),
    });
  }
  if (effects[0]?.step_kind !== firstStep) {
    throw new Error(`Turn settlement next provider is not ${firstStep}`);
  }
  if (request.terminal_closeout_required) {
    effects.push({
      step_kind: "terminal_closeout",
      action: "prepare_and_execute",
      effect_ref: `${identity.effect_id}#terminal_closeout`,
      completed_phases: [...request.completed_phases],
    });
  }
  return effects;
}

function providerExecution(
  request: TurnSettlementRequest,
  identity: SettlementIdentity,
  firstStep: ProviderStepKind,
  effects: readonly ProviderEffect[],
  receipts: SettlementResult<unknown>["receipts"],
): TurnSettlementReduction {
  const attempts = Object.entries(request.effect_attempts) as Array<
    [ProviderStepKind, PreparedEffectAttempt]
  >;
  const observations = Object.entries(request.provider_observations) as Array<
    [ProviderStepKind, ProviderObservation]
  >;
  if (attempts.length === 0) {
    if (observations.length > 0) {
      return reduction(
        settlementFailed({
          kind: "receipt_missing",
          step_kind: observations[0][0],
          reason: "Turn settlement has a provider observation without a prepared effect",
          receipts,
        }),
      );
    }
    return execution(effects);
  }

  const unexpected = attempts.find(([step]) => step !== firstStep);
  if (attempts.length !== 1 || unexpected) {
    const step = unexpected?.[0] ?? attempts[1]?.[0] ?? attempts[0][0];
    return reduction(
      settlementFailed({
        kind: "receipt_missing",
        step_kind: step,
        reason: "Prepared settlement effects do not match the next ordered provider",
        receipts,
      }),
    );
  }

  const attempt = attempts[0][1];
  const expectedRef = `${identity.effect_id}#${firstStep}`;
  if (attempt.effect_ref !== expectedRef) {
    return reduction(
      settlementFailed({
        kind: "identity_mismatch",
        step_kind: firstStep,
        reason:
          `Prepared settlement effect does not match the current operation: ` +
          `journal effect is ${attempt.effect_ref} but plan effect is ${expectedRef}`,
        receipts,
      }),
    );
  }

  const strayObservation = observations.find(([step]) => step !== firstStep);
  if (strayObservation) {
    return reduction(
      settlementFailed({
        kind: "receipt_missing",
        step_kind: strayObservation[0],
        reason: "Provider observation does not match the prepared settlement effect",
        receipts,
      }),
    );
  }
  const observation = request.provider_observations[firstStep];
  if (observation?.kind === "unknown") {
    return reduction(
      settlementFailed({
        kind: "effect_outcome_unknown",
        step_kind: firstStep,
        reason:
          observation.reason ??
          "Provider could not resolve the prepared settlement effect",
        receipts,
      }),
    );
  }
  if (
    observation?.kind === "committed" &&
    !isCommittedPayload(observation.payload)
  ) {
    return reduction(
      settlementFailed({
        kind: "receipt_missing",
        step_kind: firstStep,
        reason:
          "Provider reported a committed settlement effect without a durable committed payload",
        receipts,
      }),
    );
  }
  if (observation !== undefined) {
    return reduction(
      settlementFailed({
        kind: "effect_outcome_unknown",
        step_kind: firstStep,
        reason:
          "Prepared provider observation was not durably checkpointed by the adapter",
        receipts,
      }),
    );
  }

  const effect = effects.find((candidate) => candidate.step_kind === firstStep);
  if (!effect) {
    throw new Error(`Turn settlement has no provider effect for ${firstStep}`);
  }
  return execution([
    {
      step_kind: firstStep,
      action: "resolve_prepared",
      effect_ref: expectedRef,
      completed_phases: effect.completed_phases,
      resolution_policy: {
        committed: "checkpoint",
        absent: "execute",
        unknown: "fail_closed",
      },
    },
    ...effects.filter((candidate) => candidate.step_kind !== firstStep),
  ]);
}

/**
 * Reduce one complete Turn settlement snapshot.
 *
 * The first reduction validates identity, replay, and the committed journal
 * prefix before authorizing still-Python provider effects. The second reduces
 * their checkpointed outcomes into the canonical receipt chain and result.
 * A replay that needs no provider effect completes in one reduction.
 */
export function reduceTurnSettlementTransaction(
  value: unknown,
): TurnSettlementReduction {
  const request = decodeRequest(value);
  const identityResult = settlementIdentityFromPlan(request.transaction_plan);
  if (identityResult.failure !== null) return failedState(identityResult);

  const identity = identityResult.value;
  const matching = requireMatchingEffectId(
    request.committed_effect_id,
    identity.effect_id,
  );
  if (matching.failure !== null) return failedState(matching);

  const base = settlementNextAction({
    identity,
    ordered_steps: BASE_SETTLEMENT_STEPS,
    committed_payloads: {
      validation: {},
      durable_writeback: request.writeback_payload,
      quota_spend: request.quota_spend_payload,
    },
    completed_phases: request.completed_phases,
    transaction_phases: request.transaction_phases,
    require_validation: true,
    source_ref_prefix: "turn_journal",
  });
  if (base.decision === "failed") return failedState(base.result);
  if (base.decision === "execute") {
    if (base.step_kind === "validation" || base.step_kind === "terminal_closeout") {
      throw new Error(`unsupported base settlement step ${base.step_kind}`);
    }
    const effects = pendingProviderEffects(request, identity, base.step_kind);
    return request.failed_provider_attempt === null
      ? providerExecution(
          request,
          identity,
          base.step_kind,
          effects,
          base.result.receipts,
        )
      : providerFailure(
          identity,
          request,
          base.step_kind,
          base.result.receipts,
        );
  }

  let receipts = [...base.result.receipts];
  if (request.terminal_closeout_required) {
    if (request.terminal_closeout_payload === null) {
      const effects: readonly ProviderEffect[] = [
        {
          step_kind: "terminal_closeout",
          action: "prepare_and_execute",
          effect_ref: `${identity.effect_id}#terminal_closeout`,
          completed_phases: [...request.completed_phases],
        },
      ];
      return request.failed_provider_attempt === null
        ? providerExecution(
            request,
            identity,
            "terminal_closeout",
            effects,
            receipts,
          )
        : providerFailure(
            identity,
            request,
            "terminal_closeout",
            receipts,
          );
    }
    const terminal = seedCommittedSteps({
      identity,
      ordered_steps: ["terminal_closeout"],
      committed_payloads: {
        terminal_closeout: request.terminal_closeout_payload,
      },
      completed_phases: ["terminal_closeout"],
      transaction_phases: ["terminal_closeout"],
      require_validation: false,
      source_ref_prefix: "turn_journal",
    });
    if (terminal.failure !== null) return failedState(terminal);
    receipts = [...receipts, ...terminal.receipts];
  } else if (request.terminal_closeout_payload !== null) {
    return reduction(
      settlementFailed({
        kind: "terminal_closeout_rejected",
        step_kind: "terminal_closeout",
        reason: "Turn settlement contains an unrequested terminal closeout",
        receipts,
      }),
    );
  }

  const danglingAttempt = Object.keys(request.effect_attempts)[0] as
    | ProviderStepKind
    | undefined;
  if (danglingAttempt) {
    return reduction(
      settlementFailed({
        kind: "receipt_missing",
        step_kind: danglingAttempt,
        reason: "Turn settlement has a prepared effect after its provider phase",
        receipts,
      }),
    );
  }

  if (request.failed_provider_attempt !== null) {
    throw new Error(
      "failed_provider_attempt remains after all required settlement effects committed",
    );
  }
  return reduction(
    settlementPure(
      {
        completed_phases: [...request.completed_phases],
        writeback: request.writeback_payload,
        quota_spend: request.quota_spend_payload,
      },
      receipts,
    ),
  );
}
