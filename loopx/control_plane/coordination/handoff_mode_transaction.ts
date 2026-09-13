/** Provider-neutral mode transition: quiescence and mode share one CAS snapshot. */
import type {JsonObject} from "../effect_program.ts";
import type {AuthorityStore, AuthorityStoreReceiptResult} from "./authority_store.ts";
import {canonicalAuthorityObject, canonicalAuthoritySha256, requireAuthorityStoreId} from "./authority_store_codec.ts";
import {indexCoordinationProjection, validateCoordinationTodoReadModel} from "./coordination_projection.ts";
import {HANDOFF_MODES, HANDOFF_MODE_PLAN_SCHEMA, planHandoffMode} from "./handoff_mode_policy.ts";
import {requireBoolean, requireStringLiteral} from "../runtime_decode.ts";
import {parseIsoTimestamp} from "../runtime_timestamp.ts";
import {leaseIsActive, TASK_LEASE_SCHEMA_VERSION} from "../work_items/task_lease_acquire.ts";

export const HANDOFF_MODE_SET_SCHEMA = "loopx_coordination_handoff_mode_set_request_v0";
const RESULT_SCHEMA = "loopx_coordination_handoff_mode_set_result_v0";
const RECEIPT_SCHEMA = "loopx_coordination_handoff_mode_receipt_v0";
export interface HandoffModeSetInput {
  goal_id: string;
  operation_id: string;
  requested_mode: string;
  observed_at: string;
  dry_run: boolean;
}

function failure(reason_code: string, reason: string, failureKind?: "decision_rejection"): JsonObject {
  return {schema_version: RESULT_SCHEMA, status: "failed", changed: false, reason_code, reason,
    ...(failureKind ? {failure_kind: failureKind} : {})};
}

function replay(receipt: AuthorityStoreReceiptResult, input: HandoffModeSetInput, hash: string,
  status: "applied" | "replayed" | "recovered"): JsonObject | null {
  if (receipt.status === "missing") return null;
  if (receipt.status !== "found") return {schema_version: RESULT_SCHEMA, ...receipt, changed: false};
  const record = receipt.receipts[0];
  if (receipt.receipts.length !== 1 || record?.schema_version !== RECEIPT_SCHEMA ||
    record.goal_id !== input.goal_id || record.operation_id !== input.operation_id || record.request_sha256 !== hash) {
    return failure("coordination_operation_identity_mismatch", "operation id names another handoff mode intent",
      "decision_rejection");
  }
  const decision = canonicalAuthorityObject(record.decision, "handoff mode decision receipt");
  return {schema_version: RESULT_SCHEMA, ...decision, status,
    changed: status !== "replayed" && decision.changed === true,
    provider_revision: receipt.provider_revision, cursor: receipt.cursor};
}

export async function executeHandoffModeSet(store: AuthorityStore, raw: HandoffModeSetInput): Promise<JsonObject> {
  let input: HandoffModeSetInput;
  let now: Date;
  try {
    input = {...raw, goal_id: requireAuthorityStoreId(raw.goal_id, "goal id"),
      operation_id: requireAuthorityStoreId(raw.operation_id, "operation id"),
      requested_mode: requireStringLiteral(raw.requested_mode, HANDOFF_MODES, "requested_mode"),
      dry_run: requireBoolean(raw.dry_run, "dry_run")};
    const parsed = typeof input.observed_at === "string" ? parseIsoTimestamp(input.observed_at) : null;
    if (!parsed) throw new Error("observed_at must be a valid ISO timestamp");
    now = parsed;
  } catch (error) { return failure("invalid_handoff_mode_request", String(error)); }
  // Retry time is observation context, not a new intent. Preview never consumes an operation id.
  const hash = canonicalAuthoritySha256({goal_id: input.goal_id, requested_mode: input.requested_mode});
  if (!input.dry_run) {
    const previous = replay(await store.readReceipt(input.operation_id), input, hash, "replayed");
    if (previous) return previous;
  }
  const loaded = await store.loadAuthority();
  if (loaded.status !== "loaded") return {schema_version: RESULT_SCHEMA, ...loaded, changed: false};
  let decision: JsonObject;
  try {
    const head = loaded.head;
    const indexed = indexCoordinationProjection(head, input.goal_id);
    validateCoordinationTodoReadModel(head, input.goal_id);
    const previous = requireStringLiteral(head.handoff_mode ?? "legacy", HANDOFF_MODES, "canonical handoff_mode");
    const claimed = [...indexed.todos.values()].filter(todo => todo.archive_state === "active" &&
      todo.done !== true && typeof todo.claimed_by === "string" && todo.claimed_by.trim()).map(todo => ({
      todo_id: todo.todo_id, claimed_by: todo.claimed_by, status: todo.status}));
    const leases = [...indexed.leases.values()].filter(lease => {
      if (lease.schema_version !== TASK_LEASE_SCHEMA_VERSION) throw new Error("canonical lease schema mismatch");
      return leaseIsActive(lease, now);
    }).map(lease => ({todo_id: lease.todo_id, owner: lease.owner, expires_at: lease.expires_at}));
    const plan = planHandoffMode({schema_version: HANDOFF_MODE_PLAN_SCHEMA, previous_mode: previous,
      requested_mode: input.requested_mode, active_claimed_todo_ids: claimed.map(todo => todo.todo_id),
      active_lease_todo_ids: leases.map(lease => lease.todo_id)});
    decision = {goal_id: input.goal_id, operation_id: input.operation_id, previous_mode: previous,
      previous_mode_valid: true, handoff_mode: input.requested_mode, changed: plan.outcome === "apply"};
    if (plan.outcome === "rejected") return {...failure(String(plan.code),
      "handoff_mode can only change without unfinished claimed Todos or time-active leases",
      "decision_rejection"),
      ...decision, claimed_todos: claimed, active_leases: leases, provider_revision: loaded.provider_revision};
  } catch (error) { return failure("invalid_handoff_mode_authority", String(error)); }
  if (input.dry_run) return {schema_version: RESULT_SCHEMA, ...decision, status: "planned",
    provider_revision: loaded.provider_revision};
  // Seal even an unchanged accepted intent: retry after another mode switch must not reapply it.
  const commit = await store.commitAuthority({operation_id: input.operation_id,
    expected_provider_revision: loaded.provider_revision,
    next_projection: {...loaded.head, handoff_mode: input.requested_mode},
    events: decision.changed ? [{schema_version: "loopx_handoff_mode_changed_v0", ...decision}] : [],
    receipts: [{schema_version: RECEIPT_SCHEMA, goal_id: input.goal_id, operation_id: input.operation_id,
      request_sha256: hash, decision}]});
  return replay(await store.readReceipt(input.operation_id), input, hash,
    commit.status === "applied" ? "applied" : "recovered") ?? (commit.status === "applied"
    ? failure("coordination_commit_readback_mismatch", "applied mode transaction lacks its durable receipt")
    : {schema_version: RESULT_SCHEMA, ...commit, changed: false});
}
