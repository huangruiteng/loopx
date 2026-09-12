import type { JsonObject } from "../effect_program.ts";
import type { AuthorityStore, AuthorityStoreCommit, AuthorityStoreReceiptResult } from "./authority_store.ts";
import {
  AuthorityStoreProtocolError,
  canonicalAuthorityBytes,
  canonicalAuthorityObject,
  canonicalAuthoritySha256,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";
import {
  TODO_DOMAIN_ITEM_SCHEMA,
  canonicalCoordinationTodoRecord,
  canonicalTodoDomainRecord,
} from "./coordination_state_contract.ts";
import {
  indexCoordinationProjection,
  prepareCoordinationProjectionCommit,
  validateCoordinationTodoReadModel,
} from "./coordination_projection.ts";
import { normalizeRegisteredTodoAgents, normalizeTodoAgent } from "./todo_agents.ts";

import { evaluateCoordinationTerminalFence, COORDINATION_TERMINAL_FENCE_REQUEST_SCHEMA }
  from "./todo_lifecycle_decision.ts";
import { leaseEpoch } from "../work_items/task_lease_acquire.ts";
import { parseIsoTimestamp } from "../runtime_timestamp.ts";
import { normalizeNativePlanningIntent, planNativeTodoUpdate } from "../todos/native_update_plan.ts";

export const COORDINATION_TODO_UPDATE_REQUEST_SCHEMA =
  "loopx_local_coordination_todo_update_request_v0";
// Older runtimes must reject planning requests rather than commit only their copy patch.
export const COORDINATION_TODO_PLANNING_UPDATE_REQUEST_SCHEMA =
  "loopx_local_coordination_todo_update_request_v1";
export const COORDINATION_TODO_UPDATE_RESULT_SCHEMA =
  "loopx_coordination_todo_update_result_v0";
export const COORDINATION_TODO_UPDATE_RECEIPT_SCHEMA =
  "loopx_coordination_todo_update_receipt_v0";

const UPDATE_FIELDS = new Set(["text", "note"]);

export interface CoordinationTodoUpdateInput {
  readonly goal_id: string;
  readonly todo_id: string;
  readonly expected_role: string | null;
  readonly actor_agent_id: string | null;
  readonly registered_agents: readonly string[];
  readonly operation_id: string;
  readonly expected_provider_revision?: string;
  readonly patch: JsonObject;
  readonly clear_fields: readonly string[];
  readonly dry_run: boolean;
  readonly now: Date;
  readonly lease_idempotency_key?: string | null;
  readonly lease_expected_version?: number | null;
  readonly planning_intent?: JsonObject;
}

export type CoordinationTodoUpdateResult = JsonObject & {
  readonly schema_version: typeof COORDINATION_TODO_UPDATE_RESULT_SCHEMA;
};

function failure(code: string, reason: string): CoordinationTodoUpdateResult {
  return {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA, status: "failed",
    changed: false, reason_code: code, reason};
}

function isFailure(value: JsonObject): value is CoordinationTodoUpdateResult {
  return value.schema_version === COORDINATION_TODO_UPDATE_RESULT_SCHEMA &&
    value.status === "failed";
}

function normalizeInput(raw: CoordinationTodoUpdateInput): CoordinationTodoUpdateInput {
  const planningIntent = normalizeNativePlanningIntent(raw.planning_intent);
  const key = raw.lease_idempotency_key ?? null;
  const version = raw.lease_expected_version ?? null;
  if (key !== null && (typeof key !== "string" || !key.trim() || key !== key.trim())) {
    throw new AuthorityStoreProtocolError("lease_idempotency_key must be a non-empty unpadded string");
  }
  if (version !== null && (!Number.isSafeInteger(version) || version < 0)) {
    throw new AuthorityStoreProtocolError("lease_expected_version must be a non-negative safe integer");
  }
  const patch = canonicalAuthorityObject(raw.patch, "Todo update patch");
  const clearFields = raw.clear_fields.map((field, index) =>
    requireAuthorityStoreId(field, `clear_fields[${index}]`));
  if (Object.keys(patch).length + clearFields.length + Object.keys(planningIntent).length === 0) {
    throw new AuthorityStoreProtocolError("Todo update requires a non-empty patch");
  }
  if (new Set(clearFields).size !== clearFields.length) {
    throw new AuthorityStoreProtocolError("clear_fields must be unique");
  }
  const unsupported = [...Object.keys(patch), ...clearFields]
    .find((field) => !UPDATE_FIELDS.has(field));
  if (unsupported !== undefined) {
    throw new AuthorityStoreProtocolError(`Todo update does not own field ${unsupported}`);
  }
  if (Object.keys(patch).some((field) => clearFields.includes(field))) {
    throw new AuthorityStoreProtocolError("Todo update cannot patch and clear the same field");
  }
  if (raw.expected_role !== null && !["agent", "user"].includes(raw.expected_role)) {
    throw new AuthorityStoreProtocolError("expected_role must be agent or user");
  }
  if (typeof raw.dry_run !== "boolean") {
    throw new AuthorityStoreProtocolError("dry_run must be a boolean");
  }
  if (!(raw.now instanceof Date) || Number.isNaN(raw.now.valueOf())) {
    throw new AuthorityStoreProtocolError("now must be a valid Date");
  }
  return {...raw, planning_intent: planningIntent, lease_idempotency_key: key, lease_expected_version: version,
    goal_id: requireAuthorityStoreId(raw.goal_id, "goal id"),
    todo_id: requireAuthorityStoreId(raw.todo_id, "todo id"),
    operation_id: requireAuthorityStoreId(raw.operation_id, "operation id"),
    actor_agent_id: raw.actor_agent_id === null ? null :
      normalizeTodoAgent(raw.actor_agent_id, "actor_agent_id"),
    registered_agents: normalizeRegisteredTodoAgents(raw.registered_agents),
    patch, clear_fields: clearFields};
}

function replayUpdate(
  receipt: AuthorityStoreReceiptResult, input: CoordinationTodoUpdateInput,
  requestSha: string, status: "replayed" | "applied" | "recovered",
): CoordinationTodoUpdateResult | null {
  if (receipt.status === "missing") return null;
  if (receipt.status !== "found") {
    return {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA, ...receipt, changed: false};
  }
  const original = receipt.receipts[0];
  if (receipt.receipts.length !== 1 ||
      original?.schema_version !== COORDINATION_TODO_UPDATE_RECEIPT_SCHEMA ||
      original.operation_id !== input.operation_id || original.goal_id !== input.goal_id ||
      original.todo_id !== input.todo_id || original.request_sha256 !== requestSha ||
      typeof original.changed !== "boolean") {
    return failure("coordination_operation_identity_mismatch",
      "operation id already names a different Todo update request");
  }
  return {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA,
    status: status === "applied" && !original.changed ? "no_change" : status,
    changed: status !== "replayed" && original.changed,
    todo_id: input.todo_id, provider_revision: receipt.provider_revision,
    cursor: receipt.cursor, original_receipt: original,
    projection_delivery: original.changed ? "pending" : "not_required",
    projection_source: "committed_authority_journal"};
}

function updateRequestSha(input: CoordinationTodoUpdateInput): string {
  return canonicalAuthoritySha256({goal_id: input.goal_id,
    todo_id: input.todo_id, expected_role: input.expected_role,
    actor_agent_id: input.actor_agent_id, patch: input.patch,
    ...(input.expected_provider_revision === undefined ? {} :
      {expected_provider_revision: input.expected_provider_revision}),
    clear_fields: input.clear_fields, dry_run: input.dry_run,
    ...(Object.keys(input.planning_intent ?? {}).length ? {planning_intent: input.planning_intent} : {}),
    // Preserve receipt identity for pre-proof requests already persisted in v0.
    ...(input.lease_idempotency_key != null || input.lease_expected_version != null ? {
      lease_idempotency_key: input.lease_idempotency_key,
      lease_expected_version: input.lease_expected_version,
    } : {}),
  });
}

function loadUpdateTarget(
  head: JsonObject, input: CoordinationTodoUpdateInput,
): {todo: JsonObject; leases: ReadonlyMap<string, JsonObject>} | CoordinationTodoUpdateResult {
  try {
    validateCoordinationTodoReadModel(head, input.goal_id);
    const projection = indexCoordinationProjection(head, input.goal_id);
    const found = projection.todos.get(input.todo_id);
    return found === undefined
      ? failure("todo_not_found", "canonical Todo is missing")
      : {todo: found, leases: projection.leases};
  } catch (error) {
    return failure("invalid_coordination_projection",
      error instanceof Error ? error.message : "invalid coordination projection");
  }
}

function targetRejection(
  head: JsonObject, todo: JsonObject, leases: ReadonlyMap<string, JsonObject>,
  input: CoordinationTodoUpdateInput,
): CoordinationTodoUpdateResult | null {
  if (input.expected_role !== null && todo.role !== input.expected_role) {
    return failure("todo_role_mismatch", "Todo does not have the requested role");
  }
  if (todo.archive_state !== "active") {
    return failure("todo_archived", "Todo update requires an active Todo");
  }
  if (todo.role !== "agent" || todo.status === "done") {
    return failure("unsupported_todo_update_target",
      "native metadata update currently requires a non-completed agent Todo");
  }
  if (Array.isArray(todo.excluded_agents) && todo.excluded_agents.includes(input.actor_agent_id)) {
    return failure("actor_excluded", "Todo update actor is excluded from this Todo");
  }
  if (todo.bound_agent && todo.bound_agent !== input.actor_agent_id) {
    return failure("bound_agent_mismatch", "Todo update requires the bound agent");
  }
  // Text/note correction is not a claim or an execution transition. Registered
  // peers may edit unclaimed work, but must not edit another owner's work.
  if (todo.claimed_by && todo.claimed_by !== input.actor_agent_id) {
    return failure("update_owner_mismatch", "Todo update cannot edit another claim owner's work");
  }
  const lease = leases.get(input.todo_id);
  const mode = head.handoff_mode === undefined ? "legacy" : head.handoff_mode;
  if (typeof mode !== "string" || !["legacy", "soft_claim", "hard_lease"].includes(mode)) {
    return failure("invalid_handoff_mode", "canonical handoff mode is invalid");
  }
  if (lease !== undefined || mode === "hard_lease" ||
      input.lease_idempotency_key != null || input.lease_expected_version != null) {
    try {
      const expires = lease === undefined ? null :
        typeof lease.expires_at === "string" ? parseIsoTimestamp(lease.expires_at) : null;
      if (lease?.status === "active" && expires === null) {
        return failure("invalid_coordination_projection", "active lease expiry is invalid");
      }
      const fence = evaluateCoordinationTerminalFence({
        schema_version: COORDINATION_TERMINAL_FENCE_REQUEST_SCHEMA,
        todo, registered_agents: input.registered_agents, actor_agent_id: input.actor_agent_id,
        // A historical lease never licenses an unfenced edit. No acquisition or override.
        handoff_mode: lease !== undefined ? "hard_lease" : mode,
        lease: lease === undefined ? null : {...lease, present: true,
          active: lease.status === "active" && expires !== null && expires > input.now,
          lease_epoch: leaseEpoch(lease)},
        lease_idempotency_key: input.lease_idempotency_key ?? null,
        lease_expected_version: input.lease_expected_version ?? null,
        allow_user_gate_auto_acquire: false, delegated_authority: false,
        require_active_when_fence_supplied: true,
      });
      if (fence.outcome !== "apply") {
        return failure(String(fence.code), "Todo update requires the current active lease execution proof");
      }
      if (lease !== undefined && todo.claimed_by !== input.actor_agent_id) {
        return failure("update_owner_mismatch", "Leased Todo update requires the current claim owner");
      }
      const status = input.planning_intent?.status;
      if (lease !== undefined && typeof status === "string" && status.toLowerCase() !== todo.status) {
        return failure("update_lease_status_transition_unsupported",
          "Changing a leased Todo status requires an atomic lifecycle operation; planning update leaves the lease unchanged");
      }
    } catch (error) {
      return failure("invalid_coordination_projection",
        error instanceof Error ? error.message : "invalid lease facts");
    }
  }
  return null;
}

function prepareUpdatedTodo(
  todo: JsonObject, input: CoordinationTodoUpdateInput, head: JsonObject,
): {next: JsonObject; changed: boolean; clearFields: string[]} | CoordinationTodoUpdateResult {
  const next: JsonObject = {...todo, ...input.patch};
  for (const field of input.clear_fields) delete next[field];
  // Preserve the public planner's legacy metadata semantics. Raw copy edits
  // already carry actor attribution, while planning-only updates historically
  // leave last_actor_agent_id untouched.
  const rawCopyChanged = Object.entries(input.patch).some(([field, value]) =>
    !Object.hasOwn(todo, field) || !canonicalAuthorityBytes(todo[field]).equals(canonicalAuthorityBytes(value))) ||
    input.clear_fields.some(field => Object.hasOwn(todo, field));
  if (rawCopyChanged) {
    next.last_actor_agent_id = input.actor_agent_id;
  }
  next.updated_at = input.now.toISOString().replace(/\.\d{3}Z$/u, "Z");
  const clearFields = new Set(input.clear_fields);
  try {
    if (Object.keys(input.planning_intent ?? {}).length) {
      const updates = planNativeTodoUpdate(todo, input.planning_intent!, head,
        input.actor_agent_id, input.registered_agents, String(next.updated_at));
      for (const [field, value] of Object.entries(updates)) {
        if (value === null) { delete next[field]; clearFields.add(field); }
        else next[field] = value;
      }
      next.done = next.status === "done" || next.status === "deferred";
    }
    if (todo.schema_version === TODO_DOMAIN_ITEM_SCHEMA) {
      canonicalTodoDomainRecord(next, "updated Todo");
    } else {
      canonicalCoordinationTodoRecord(next, "updated Todo");
    }
  } catch (error) {
    return failure("invalid_coordination_todo_update",
      error instanceof Error ? error.message : "invalid updated Todo");
  }
  const changedBeforeAudit = {...next};
  delete changedBeforeAudit.last_actor_agent_id;
  delete changedBeforeAudit.updated_at;
  const originalBeforeAudit = {...todo};
  delete originalBeforeAudit.last_actor_agent_id;
  delete originalBeforeAudit.updated_at;
  const changed = !canonicalAuthorityBytes(changedBeforeAudit).equals(
    canonicalAuthorityBytes(originalBeforeAudit));
  if (!changed) {
    next.last_actor_agent_id = todo.last_actor_agent_id;
    next.updated_at = todo.updated_at;
  }
  return {next, changed, clearFields: [...clearFields]};
}

/** Update mutable Todo metadata from the canonical provider head. */
export async function executeCoordinationTodoUpdate(
  store: AuthorityStore, rawInput: CoordinationTodoUpdateInput,
): Promise<CoordinationTodoUpdateResult> {
  let input: CoordinationTodoUpdateInput;
  try { input = normalizeInput(rawInput); } catch (error) {
    return failure("invalid_coordination_todo_update",
      error instanceof Error ? error.message : "invalid Todo update");
  }
  const requestSha = updateRequestSha(input);
  const replay = replayUpdate(await store.readReceipt(input.operation_id), input, requestSha, "replayed");
  if (replay !== null) return replay;
  if (input.actor_agent_id === null || !input.registered_agents.includes(input.actor_agent_id)) {
    return failure("actor_not_registered", "Todo update requires a registered actor");
  }
  const head = await store.loadAuthority();
  if (head.status !== "loaded") {
    return {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA, ...head, changed: false};
  }
  if (input.expected_provider_revision !== undefined &&
      input.expected_provider_revision !== head.provider_revision) {
    return failure("provider_revision_mismatch", "Current revision changed; inspect again before continuing");
  }

  const target = loadUpdateTarget(head.head, input);
  if (isFailure(target)) return target;
  const rejected = targetRejection(head.head, target.todo, target.leases, input);
  if (rejected !== null) return rejected;
  const prepared = prepareUpdatedTodo(target.todo, input, head.head);
  if (isFailure(prepared)) return prepared;
  const {next, changed, clearFields} = prepared;
  if (input.dry_run) return {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA,
    status: changed ? "planned" : "no_change", changed, todo_id: input.todo_id,
    provider_revision: head.provider_revision, cursor: head.cursor, dry_run: true};
  const commit: AuthorityStoreCommit = changed ? prepareCoordinationProjectionCommit({
    goal_id: input.goal_id, operation_id: input.operation_id,
    expected_provider_revision: head.provider_revision, projection: head.head,
    mutations: [{kind: "todo_upsert", todo: next, clear_fields: clearFields}],
  }) : {operation_id: input.operation_id,
    expected_provider_revision: head.provider_revision, next_projection: head.head,
    events: [], receipts: []};
  commit.receipts = [{schema_version: COORDINATION_TODO_UPDATE_RECEIPT_SCHEMA,
    operation_id: input.operation_id, goal_id: input.goal_id,
    todo_id: input.todo_id, request_sha256: requestSha, changed}];
  const committed = await store.commitAuthority(commit);
  const readback = replayUpdate(await store.readReceipt(input.operation_id), input, requestSha,
    committed.status === "applied" ? "applied" : "recovered");
  if (readback !== null) return readback;
  return committed.status === "applied"
    ? failure("coordination_commit_readback_mismatch", "applied update lacks its durable receipt")
    : {schema_version: COORDINATION_TODO_UPDATE_RESULT_SCHEMA, ...committed, changed: false};
}
