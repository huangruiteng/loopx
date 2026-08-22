import type { JsonObject } from "../effect_program.ts";
import {
  optionalNonEmptyString,
  requireJsonObject,
  requireNonEmptyString,
} from "../runtime_decode.ts";
import {
  isLocalTodoCompletionIdentity,
  localTodoCompletionIdentity,
} from "../todos/completion_fence.ts";

export const REPLAN_SETTLEMENT_REQUEST_SCHEMA =
  "loopx_replan_settlement_request_v0";
export const REPLAN_SETTLEMENT_CONTRACT_SCHEMA =
  "replan_settlement_contract_v0";
export const TODO_LIFECYCLE_REENTRY_REQUEST_SCHEMA =
  "loopx_todo_lifecycle_reentry_request_v0";
export const TODO_LIFECYCLE_REENTRY_SCHEMA =
  "todo_lifecycle_settlement_reentry_v0";

function shellArgument(value: string): string {
  if (/^[A-Za-z0-9_./:@%+=,-]+$/.test(value)) return value;
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}

function argumentSuffix(values: readonly string[]): string {
  return values.length > 0
    ? ` ${values.map(shellArgument).join(" ")}`
    : "";
}

function lifecycleTrigger(value: unknown, index: number): JsonObject {
  const trigger = requireJsonObject(value, `triggers[${index}]`);
  if (trigger.kind !== "completed_advancement_without_successor") {
    throw new Error(`triggers[${index}].kind is unsupported`);
  }
  return {
    kind: trigger.kind,
    todo_id: requireNonEmptyString(
      trigger.todo_id,
      `triggers[${index}].todo_id`,
    ),
    completion_turn_key: optionalNonEmptyString(
      trigger.completion_turn_key,
      `triggers[${index}].completion_turn_key`,
    ),
  };
}

export function projectTodoLifecycleSettlementReentry(value: unknown): JsonObject {
  const request = requireJsonObject(
    value,
    "work_item.replan_settlement.reentry params",
  );
  if (request.schema_version !== TODO_LIFECYCLE_REENTRY_REQUEST_SCHEMA) {
    throw new Error("Todo lifecycle reentry request schema mismatch");
  }
  const goalId = requireNonEmptyString(request.goal_id, "goal_id");
  if (!Array.isArray(request.triggers) || request.triggers.length === 0) {
    throw new Error("triggers must be a non-empty array");
  }
  const triggers = request.triggers.slice(0, 3).map(lifecycleTrigger).map(
    (trigger) => {
      const todoId = String(trigger.todo_id);
      const persistedKey = trigger.completion_turn_key;
      const completionIdentityKey = typeof persistedKey === "string"
        ? persistedKey
        : localTodoCompletionIdentity(goalId, todoId);
      return {
        kind: trigger.kind,
        todo_id: todoId,
        completion_turn_key: completionIdentityKey,
        completion_identity_source: isLocalTodoCompletionIdentity(
            completionIdentityKey,
          )
          ? "unscoped_completion"
          : "turn_settlement",
      };
    },
  );
  const lifecycleActorArgs = Array.isArray(request.lifecycle_actor_args)
    ? request.lifecycle_actor_args.map((item, index) =>
      requireNonEmptyString(item, `lifecycle_actor_args[${index}]`)
    )
    : [];
  const quotaScopedArgs = Array.isArray(request.quota_scoped_args)
    ? request.quota_scoped_args.map((item, index) =>
      requireNonEmptyString(item, `quota_scoped_args[${index}]`)
    )
    : [];
  const nextCliActions = triggers.map((trigger) => {
    const todoId = String(trigger.todo_id);
    const completionIdentityKey = String(trigger.completion_turn_key);
    const completionIdentityArgs =
      trigger.completion_identity_source === "unscoped_completion"
        ? ["--completion-identity-key", completionIdentityKey]
        : ["--turn-instance-id", completionIdentityKey];
    return (
      `when no real successor remains for completed Todo ${todoId}: ` +
      `loopx todo complete --goal-id ${shellArgument(goalId)} ` +
      `--todo-id ${shellArgument(todoId)}` +
      argumentSuffix(completionIdentityArgs) +
      argumentSuffix(lifecycleActorArgs) +
      " --no-follow-up --note '<public-safe no-follow-up rationale>'"
    );
  });
  nextCliActions.push(
    "otherwise link or create one real runnable successor for the exact " +
      "completed Todo; do not create lifecycle-only filler",
    `loopx --format json quota should-run --goal-id ${shellArgument(goalId)}` +
      argumentSuffix(quotaScopedArgs),
  );
  return {
    schema_version: TODO_LIFECYCLE_REENTRY_SCHEMA,
    resolution_mode: "todo_lifecycle_settlement",
    triggers,
    next_cli_actions: nextCliActions,
  };
}

export function projectReplanSettlementContract(value: unknown): JsonObject {
  const request = requireJsonObject(value, "work_item.replan_settlement params");
  if (request.schema_version !== REPLAN_SETTLEMENT_REQUEST_SCHEMA) {
    throw new Error("Replan settlement request schema mismatch");
  }
  const selectedTodoId = optionalNonEmptyString(
    request.selected_todo_id,
    "selected_todo_id",
  );
  const semanticObligationId = requireNonEmptyString(
    request.semantic_replan_obligation_id,
    "semantic_replan_obligation_id",
  );
  const semanticObligationSettlementBound = selectedTodoId === null;
  const settlementBindingKind = semanticObligationSettlementBound
    ? "autonomous_replan"
    : "todo";
  const settlementBindingId = selectedTodoId ?? semanticObligationId;

  return {
    schema_version: REPLAN_SETTLEMENT_CONTRACT_SCHEMA,
    single_binding_required: true,
    settlement_binding: {
      kind: settlementBindingKind,
      id: settlementBindingId,
      cli_argument: semanticObligationSettlementBound
        ? "--replan-obligation-id"
        : "--todo-id",
    },
    semantic_obligation: {
      kind: "autonomous_replan",
      id: semanticObligationId,
      settlement_bound: semanticObligationSettlementBound,
      discharge: semanticObligationSettlementBound
        ? "direct_settlement"
        : "todo_bound_writeback",
    },
  };
}
