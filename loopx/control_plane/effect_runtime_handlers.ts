import {
  effectIdsMatch,
  effectProgramFromOrderedSteps,
  interpretQuotaShouldRunPacket,
  interpretTurnResultPacket,
  settlementBindGate,
  settlementBindReduce,
  settlementReceipt,
  settlementIdentity,
  settlementIdentityPayload,
  settlementPlanPayload,
  settlementResultPayload,
  SETTLEMENT_FAILURE_KINDS,
  SETTLEMENT_STEP_KINDS,
  type JsonObject,
  type SettlementFailure,
  type SettlementFailureKind,
  type SettlementIdentityInput,
  type SettlementPlan,
  type SettlementReceipt,
  type SettlementResult,
  type SettlementStep,
  type SettlementStepKind,
} from "./effect_program.ts";
import {
  optionalNonEmptyString as optionalString,
  requireJsonObject as requiredObject,
  requireNonEmptyString as requiredString,
  requireStringArray as stringArray,
  requireStringLiteral,
} from "./runtime_decode.ts";
import {
  governedCapabilitySettlementStatus,
  validateGovernedCapabilityAdmission,
  validateGovernedCapabilityResult,
  validateGovernedCapabilitySettlementCallback,
} from "./governed_capability.ts";
import { evaluateDeliveryWorkspaceCausality } from "./quota/settlement_workspace_causality.ts";
import {
  interpretTurnJournal,
  type TurnJournalInspectionRequest,
} from "./turn_driver/turn_journal.ts";
import { commitTurnJournal } from "./turn_driver/turn_journal_effects.ts";
import {
  evaluateTodoCompletionFence,
  projectTodoCompletionIdentity,
} from "./todos/completion_fence.ts";
import {
  buildTodoCompletionMetadataUpdates,
  normalizeTodoCompletionValue,
  requireTodoCompletionMetadataValue,
  selectTodoCompletionContinuation,
  selectTodoCompletionState,
} from "./todos/completion_state.ts";
import { evaluateTodoCompletionValidationPlan } from "./todos/completion_validation_plan.ts";
import { transitionTodoNextAction } from "./todos/next_action.ts";
import { evaluateSchedulerStateTransition } from "./scheduler/state_transition_rules.ts";
import {
  evaluateSchedulerStateOperation,
  loadSchedulerState,
  writeSchedulerState,
} from "./scheduler/state_store.ts";
import { buildVisionCheckpoint } from "./goals/vision_checkpoint.ts";
import {
  evaluateDeliveryRoute,
} from "./turn_driver/delivery_continuity.ts";
import { reduceTurnSettlementTransaction } from "./turn_driver/settlement.ts";
import {
  projectReplanSettlementContract,
  projectTodoLifecycleSettlementReentry,
} from "./work_items/replan_settlement.ts";

type EffectRuntimeHandler = (params: JsonObject) => unknown | Promise<unknown>;

export interface EffectRuntimeHandlerContext {
  fingerprint: string;
  requestShutdown: () => void;
}

function asObject(value: unknown): JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as JsonObject)
    : {};
}

function settlementStepKind(value: unknown, label: string): SettlementStepKind {
  return requireStringLiteral(
    value,
    SETTLEMENT_STEP_KINDS,
    label,
    `${label} has an unsupported settlement step kind`,
  );
}

function settlementFailureKind(
  value: unknown,
  label: string,
): SettlementFailureKind {
  return requireStringLiteral(
    value,
    SETTLEMENT_FAILURE_KINDS,
    label,
    `${label} has an unsupported settlement failure kind`,
  );
}

function settlementIdentityInput(
  value: unknown,
  label = "identity",
): SettlementIdentityInput {
  const input = requiredObject(value, label);
  return {
    goal_id: requiredString(input.goal_id, `${label}.goal_id`),
    agent_id: requiredString(input.agent_id, `${label}.agent_id`),
    todo_id: optionalString(input.todo_id, `${label}.todo_id`),
    turn_instance_id: requiredString(
      input.turn_instance_id,
      `${label}.turn_instance_id`,
    ),
    replan_obligation_id: optionalString(
      input.replan_obligation_id,
      `${label}.replan_obligation_id`,
    ),
  };
}

function settlementReceiptInput(
  value: unknown,
  label: string,
): SettlementReceipt {
  const receipt = requiredObject(value, label);
  return {
    step_kind: settlementStepKind(receipt.step_kind, `${label}.step_kind`),
    status: requiredString(receipt.status, `${label}.status`),
    effect_id: requiredString(receipt.effect_id, `${label}.effect_id`),
    ...(optionalString(receipt.source_ref, `${label}.source_ref`)
      ? { source_ref: optionalString(receipt.source_ref, `${label}.source_ref`)! }
      : {}),
  };
}

function settlementFailureInput(value: unknown, label: string): SettlementFailure {
  const failure = requiredObject(value, label);
  const details = failure.details === undefined
    ? undefined
    : requiredObject(failure.details, `${label}.details`);
  return {
    kind: settlementFailureKind(failure.kind, `${label}.kind`),
    step_kind: settlementStepKind(failure.step_kind, `${label}.step_kind`),
    reason: requiredString(failure.reason, `${label}.reason`),
    ...(details ? { details } : {}),
  };
}

function settlementResultInput(value: unknown, label: string): SettlementResult {
  const result = requiredObject(value, label);
  if (!Array.isArray(result.receipts)) {
    throw new Error(`${label}.receipts must be an array`);
  }
  const receipts = result.receipts.map((receipt, index) =>
    settlementReceiptInput(receipt, `${label}.receipts[${index}]`)
  );
  if (result.failure === null) {
    return { value: result.value, receipts, failure: null };
  }
  if (result.value !== null) {
    throw new Error(`${label} cannot carry both a value and a failure`);
  }
  return {
    value: null,
    receipts,
    failure: settlementFailureInput(result.failure, `${label}.failure`),
  };
}

function settlementStepInput(value: unknown, label: string): SettlementStep {
  const step = requiredObject(value, label);
  if (step.conditional !== undefined && step.conditional !== true) {
    throw new Error(`${label}.conditional must be true when present`);
  }
  return {
    kind: settlementStepKind(step.kind, `${label}.kind`),
    owner: requiredString(step.owner, `${label}.owner`),
    precondition: requiredString(step.precondition, `${label}.precondition`),
    idempotency_key_ref: requiredString(
      step.idempotency_key_ref,
      `${label}.idempotency_key_ref`,
    ),
    expected_receipt: requiredString(
      step.expected_receipt,
      `${label}.expected_receipt`,
    ),
    ...(optionalString(step.command_template, `${label}.command_template`)
      ? {
          command_template: optionalString(
            step.command_template,
            `${label}.command_template`,
          )!,
        }
      : {}),
    ...(step.conditional === true ? { conditional: true } : {}),
  };
}

function settlementPlanInput(value: unknown, label: string): SettlementPlan {
  const plan = requiredObject(value, label);
  if (!Array.isArray(plan.steps)) {
    throw new Error(`${label}.steps must be an array`);
  }
  return {
    identity: settlementIdentity(settlementIdentityInput(plan.identity, `${label}.identity`)),
    steps: plan.steps.map((step, index) =>
      settlementStepInput(step, `${label}.steps[${index}]`)
    ),
  };
}

function turnJournalInspectionRequest(
  value: unknown,
): TurnJournalInspectionRequest {
  const request = requiredObject(value, "turn_journal.inspect params");
  if (
    request.schema_version !==
      "loopx_turn_journal_interpretation_request_v0"
  ) {
    throw new Error("Turn-journal interpretation request schema mismatch");
  }
  return {
    schema_version: request.schema_version,
    journal: requiredObject(request.journal, "turn_journal.inspect journal"),
    goal_id: requiredString(request.goal_id, "turn_journal.inspect goal_id"),
    agent_id: requiredString(request.agent_id, "turn_journal.inspect agent_id"),
    turn_key: requiredString(request.turn_key, "turn_journal.inspect turn_key"),
  };
}

export function createEffectRuntimeHandlers(
  context: EffectRuntimeHandlerContext,
): ReadonlyMap<string, EffectRuntimeHandler> {
  return new Map<string, EffectRuntimeHandler>([
    [
      "runtime.ping",
      () => ({ ready: true, pid: process.pid, fingerprint: context.fingerprint }),
    ],
    [
      "runtime.shutdown",
      () => {
        context.requestShutdown();
        return { stopped: true };
      },
    ],
    [
      "turn_journal.inspect",
      (params) => interpretTurnJournal(turnJournalInspectionRequest(params)),
    ],
    ["turn_journal.write", commitTurnJournal],
    ["todo.completion_fence.evaluate", evaluateTodoCompletionFence],
    ["todo.completion_state.normalize", normalizeTodoCompletionValue],
    ["todo.completion_state.require_metadata", requireTodoCompletionMetadataValue],
    ["todo.completion_state.continuation_for_write", selectTodoCompletionContinuation],
    ["todo.completion_state.evaluate", selectTodoCompletionState],
    ["todo.completion_state.metadata_updates", buildTodoCompletionMetadataUpdates],
    ["todo.completion_validation.plan", evaluateTodoCompletionValidationPlan],
    ["todo.next_action.transition", transitionTodoNextAction],
    ["scheduler.state_transition.evaluate", evaluateSchedulerStateTransition],
    ["scheduler.state.evaluate", evaluateSchedulerStateOperation],
    ["scheduler.state.load", loadSchedulerState],
    ["scheduler.state.write", writeSchedulerState],
    ["turn.delivery_route.evaluate", evaluateDeliveryRoute],
    ["goal.vision_checkpoint.evaluate", buildVisionCheckpoint],
    [
      "quota.delivery_workspace_causality.evaluate",
      evaluateDeliveryWorkspaceCausality,
    ],
    [
      "effect.program_from_ordered_steps",
      (params) => effectProgramFromOrderedSteps(
        Array.isArray(params.ordered_steps) ? params.ordered_steps : [],
        typeof params.execution_mode === "string" ? params.execution_mode : null,
      ),
    ],
    [
      "effect.interpret_quota",
      (params) => interpretQuotaShouldRunPacket(
        asObject(params.packet),
        asObject(params.identity),
      ),
    ],
    [
      "effect.interpret_turn_result",
      (params) => interpretTurnResultPacket(
        asObject(params.packet),
        asObject(params.identity),
      ),
    ],
    [
      "governed_capability.validate_admission",
      (params) => validateGovernedCapabilityAdmission({
        admission: params.admission,
        todo_id: requiredString(params.todo_id, "todo_id"),
        todo_contract: params.todo_contract,
      }),
    ],
    [
      "governed_capability.validate_result",
      (params) => validateGovernedCapabilityResult({
        value: params.value,
        invocation_id: requiredString(params.invocation_id, "invocation_id"),
        effect_id: requiredString(params.effect_id, "effect_id"),
        result_schema: requiredString(params.result_schema, "result_schema"),
        effect_class: requiredString(params.effect_class, "effect_class"),
      }),
    ],
    [
      "governed_capability.validate_settlement_callback",
      (params) => validateGovernedCapabilitySettlementCallback({
        payload: params.payload,
        effect_id: requiredString(params.effect_id, "effect_id"),
        effect_receipt_digest: requiredString(
          params.effect_receipt_digest,
          "effect_receipt_digest",
        ),
        require_receipt_digest: params.require_receipt_digest === true,
      }),
    ],
    [
      "governed_capability.settlement_status",
      (params) => governedCapabilitySettlementStatus(params.failure),
    ],
    [
      "settlement.identity",
      (params) => settlementIdentity(settlementIdentityInput(params)),
    ],
    [
      "settlement.identity_full",
      (params) => {
        const identity = settlementIdentity(
          settlementIdentityInput(params),
        );
        return { identity, payload: settlementIdentityPayload(identity) };
      },
    ],
    [
      "settlement.effect_ids_match",
      (params) => effectIdsMatch(
        typeof params.committed_effect_id === "string"
          ? params.committed_effect_id
          : null,
        requiredString(params.expected_effect_id, "expected_effect_id"),
      ),
    ],
    [
      "settlement.receipt",
      (params) => settlementReceipt(
        settlementIdentityInput(params.identity),
        settlementStepKind(params.step_kind, "step_kind"),
        typeof params.source_ref === "string" ? params.source_ref : undefined,
      ),
    ],
    [
      "settlement.bind_gate",
      (params) => settlementBindGate(settlementResultInput(params.result, "result")),
    ],
    [
      "settlement.bind_reduce",
      (params) => settlementBindReduce(
        settlementResultInput(params.current, "current"),
        settlementResultInput(params.next, "next"),
      ),
    ],
    [
      "settlement.plan_payload",
      (params) => settlementPlanPayload(settlementPlanInput(params.plan, "plan")),
    ],
    [
      "settlement.result_payload",
      (params) => settlementResultPayload(
        settlementResultInput(params.result, "result"),
      ),
    ],
    ["turn.settlement.reduce", reduceTurnSettlementTransaction],
    ["todo.completion_identity.project", projectTodoCompletionIdentity],
    ["work_item.replan_settlement.project", projectReplanSettlementContract],
    [
      "work_item.replan_settlement.reentry",
      projectTodoLifecycleSettlementReentry,
    ],
  ]);
}

export async function dispatchEffectRuntimeMethod(
  handlers: ReadonlyMap<string, EffectRuntimeHandler>,
  method: string,
  params: JsonObject,
): Promise<unknown> {
  const handler = handlers.get(method);
  if (!handler) throw new Error("unsupported Effect runtime method");
  return await handler(params);
}
