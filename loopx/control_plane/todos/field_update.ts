/** Pure field intent planning. Admission, leases, validation and commit stay
 * with the calling lifecycle transaction; this result grants no write right. */
import type { JsonObject } from "../effect_program.ts";
import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import { requireJsonObject, requireNonEmptyString } from "../runtime_decode.ts";
import { normalizeTodoAgent, stripPythonWhitespace } from "../coordination/todo_agents.ts";
import { AuthorityStoreProtocolError } from "../coordination/authority_store_codec.ts";
import {
  buildTodoCompletionMetadataUpdates,
  TODO_COMPLETION_STATE_REQUEST_SCHEMA,
} from "./completion_state.ts";
import { normalizeTodoResumeWhen, TODO_RESUME_NORMALIZE_REQUEST_SCHEMA_VERSION } from "./resume_condition.ts";

export const TODO_FIELD_UPDATE_REQUEST_SCHEMA = "loopx_todo_field_update_request_v0";
export const TODO_FIELD_UPDATE_RESULT_SCHEMA = "loopx_todo_field_update_result_v0";

const STATUS = ["open", "done", "blocked", "deferred"] as const;
type Status = typeof STATUS[number];
export interface TodoFieldUpdatePlan extends JsonObject {
  schema_version: typeof TODO_FIELD_UPDATE_RESULT_SCHEMA;
  normalized_status: Status | null;
  target_status: Status;
  metadata_updates: JsonObject;
}
const STRING_FIELDS = ["note", "evidence", "completion_turn_key", "reason", "task_class",
  "action_kind", "task_domain", "task_repository", "continuation_policy"] as const;
const PRESENT_FIELDS = ["required_write_scopes", "required_capabilities", "target_capabilities",
  "explore_result_node_refs", "decision_scope", "required_decision_scopes", "decision_outcome",
  "decision_scope_outcomes"] as const;
const MONITOR_FIELDS = ["target_key", "monitor_effect_id", "cadence", "next_due_at", "expires_at",
  "last_checked_at", "result_hash", "consecutive_no_change", "material_change",
  "material_change_generation", "max_no_change_before_replan", "watch_only"] as const;
const FLAGS = ["clear_claim", "claim_only", "clear_user_binding", "clear_blocks_agent",
  "clear_global_gate", "clear_resume_when"] as const;
const INTENT_FIELDS = new Set<string>([...STRING_FIELDS, ...PRESENT_FIELDS, ...FLAGS,
  "status", "claimed_by", "bound_agent", "goal_bound", "blocks_agent", "excluded_agents",
  "global_gate", "unblocks_todo_id", "successor_todo_ids", "completion_continuation",
  "completion_recovery", "completion_metadata_updates_override", "resume_when",
  "resume_monitor_generation", "no_followup", "monitor_metadata"]);

function optionalString(value: unknown, label: string): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") throw new EffectRuntimeRequestError(`${label} must be a string or null`);
  return value;
}

function present(value: unknown): boolean {
  return value !== null && value !== undefined;
}

// Imported Markdown may carry an invalid historical claim. Match the existing
// codec's nullable normalization instead of treating that token as ownership.
function existingAgent(value: unknown): string | null {
  try {
    return normalizeTodoAgent(value, "agent_id");
  } catch (error) {
    if (error instanceof AuthorityStoreProtocolError) return null;
    throw error;
  }
}

function validateIntent(value: unknown): JsonObject {
  const intent = requireJsonObject(value, "Todo field intent");
  for (const key of Object.keys(intent)) {
    if (!INTENT_FIELDS.has(key)) throw new EffectRuntimeRequestError(`Todo field plan does not own ${key}`);
  }
  for (const field of [...FLAGS, "goal_bound", "global_gate", "no_followup"]) {
    if (present(intent[field]) && typeof intent[field] !== "boolean") {
      throw new EffectRuntimeRequestError(`${field} must be a boolean`);
    }
  }
  for (const field of [...STRING_FIELDS, "status", "claimed_by", "bound_agent", "blocks_agent",
    "unblocks_todo_id", "resume_when", "completion_continuation", "completion_recovery"]) {
    optionalString(intent[field], field);
  }
  return intent;
}

function validateRepair(block: JsonObject, intent: JsonObject, todoId: string): void {
  const removed = stripPythonWhitespace(String(block.removed_continuation_policy ?? "")).toLowerCase();
  if (removed !== "primary_review" && removed !== "review_handoff") return;
  const prefix = `todo_id '${todoId}' uses removed continuation_policy=${removed}; `;
  if (intent.claim_only) throw new EffectRuntimeRequestError(prefix + "repair it before claiming");
  const repair = stripPythonWhitespace(String(intent.continuation_policy ?? "")).toLowerCase();
  const exclusions = Array.isArray(intent.excluded_agents) ? intent.excluded_agents : [];
  if (repair !== "independent_handoff" || !exclusions.some(agent => existingAgent(agent) !== null)) {
    throw new EffectRuntimeRequestError(prefix +
      "repair it explicitly with continuation_policy=independent_handoff and excluded_agents=<author>");
  }
}

function bindingUpdates(block: JsonObject, intent: JsonObject, todoId: string): JsonObject {
  const updates: JsonObject = {};
  if (intent.clear_claim) updates.claimed_by = null;
  else if (intent.claimed_by) {
    const existing = existingAgent(block.claimed_by);
    if (intent.claim_only && existing && existing !== intent.claimed_by) {
      throw new EffectRuntimeRequestError(`todo_id '${todoId}' is already claimed_by='${existing}'; ` +
        "clear or transfer the claim explicitly before claiming it");
    }
    updates.claimed_by = intent.claimed_by;
  }
  if (intent.clear_user_binding) {
    updates.bound_agent = null;
    updates.goal_bound = null;
  } else if (intent.bound_agent) {
    updates.bound_agent = intent.bound_agent;
    updates.goal_bound = null;
  } else if (present(intent.goal_bound)) {
    updates.bound_agent = null;
    updates.goal_bound = intent.goal_bound;
  }
  if (intent.blocks_agent) updates.blocks_agent = intent.blocks_agent;
  else if (intent.clear_blocks_agent) updates.blocks_agent = null;
  if (present(intent.excluded_agents)) updates.excluded_agents = intent.excluded_agents;
  if (intent.clear_global_gate) updates.global_gate = null;
  else if (present(intent.global_gate)) updates.global_gate = intent.global_gate;
  return updates;
}

function completionUpdates(block: JsonObject, intent: JsonObject, targetStatus: Status,
  normalizedStatus: Status | null): JsonObject {
  if (present(intent.completion_metadata_updates_override)) {
    const updates = requireJsonObject(intent.completion_metadata_updates_override, "completion metadata override");
    if (Object.entries(updates).some(([key, value]) =>
      !["completion_continuation", "completion_recovery"].includes(key) || typeof value !== "string")) {
      throw new EffectRuntimeRequestError("TypeScript Todo completion metadata updates shape mismatch");
    }
    return {...updates};
  }
  const result = buildTodoCompletionMetadataUpdates({
    schema_version: TODO_COMPLETION_STATE_REQUEST_SCHEMA,
    block: {no_followup: block.no_followup ?? "", completion_continuation: block.completion_continuation ?? "",
      successor_todo_ids: block.successor_todo_ids ?? []},
    target_status: targetStatus, normalized_status: normalizedStatus,
    completion_continuation: intent.completion_continuation ?? null,
    completion_recovery: intent.completion_recovery ?? null,
    no_followup: intent.no_followup ?? null, successor_todo_ids: intent.successor_todo_ids ?? null,
  });
  return requireJsonObject(result.updates, "completion metadata updates");
}

export function planTodoFieldUpdate(value: unknown): TodoFieldUpdatePlan {
  const request = requireJsonObject(value, "Todo field update request");
  if (request.schema_version !== TODO_FIELD_UPDATE_REQUEST_SCHEMA) {
    throw new EffectRuntimeRequestError("Todo field update request schema mismatch");
  }
  const block = requireJsonObject(request.todo, "Todo field update source");
  const todoId = requireNonEmptyString(block.todo_id, "todo_id");
  const updatedAt = requireNonEmptyString(request.updated_at, "updated_at");
  const intent = validateIntent(request.intent);
  const resumeWhen = intent.resume_when ? normalizeTodoResumeWhen({
    schema_version: TODO_RESUME_NORMALIZE_REQUEST_SCHEMA_VERSION, resume_when: intent.resume_when,
  }) : null;
  if (intent.resume_when && !resumeWhen) throw new EffectRuntimeRequestError("unsupported Todo resume condition");
  if (resumeWhen && intent.clear_resume_when) {
    throw new EffectRuntimeRequestError("todo update accepts either resume_when or clear_resume_when, not both");
  }
  validateRepair(block, intent, todoId);
  const status = intent.status ? stripPythonWhitespace(String(intent.status)).toLowerCase() : null;
  if (status !== null && !STATUS.includes(status as Status)) {
    throw new EffectRuntimeRequestError("todo status must be one of: open, done, blocked, deferred");
  }
  const normalizedStatus = status as Status | null;
  const targetStatus = normalizedStatus ?? (block.status || "open") as Status;
  if (!STATUS.includes(targetStatus)) throw new EffectRuntimeRequestError("invalid source Todo status");
  if (targetStatus === "deferred" && intent.clear_resume_when) {
    throw new EffectRuntimeRequestError("cannot clear resume_when while todo status remains deferred");
  }
  if (intent.claim_only && targetStatus !== "open") {
    throw new EffectRuntimeRequestError(`todo claim requires status=open; todo_id '${todoId}' is status='${targetStatus}'`);
  }
  const updates: JsonObject = {todo_id: todoId, status: targetStatus};
  if (normalizedStatus === "done" && !block.completed_at) updates.completed_at = updatedAt;
  else if (normalizedStatus && normalizedStatus !== "done") updates.completed_at = null;
  // The public editing contract distinguishes omitted/empty text metadata from
  // present collections and booleans. Never turn [] or false into omission.
  for (const field of STRING_FIELDS) if (intent[field]) updates[field] = intent[field];
  for (const field of PRESENT_FIELDS) if (present(intent[field])) updates[field] = intent[field];
  Object.assign(updates, bindingUpdates(block, intent, todoId));
  if (intent.unblocks_todo_id) updates.unblocks_todo_id = intent.unblocks_todo_id;
  if (present(intent.successor_todo_ids)) updates.successor_todo_ids = intent.successor_todo_ids;
  if (intent.clear_resume_when) {
    updates.resume_when = null;
    updates.resume_monitor_generation = null;
  } else if (resumeWhen) {
    updates.resume_when = resumeWhen;
    updates.resume_monitor_generation = resumeWhen.startsWith("monitor_changed:")
      ? intent.resume_monitor_generation ?? null : null;
  }
  if (present(intent.no_followup)) updates.no_followup = intent.no_followup;
  Object.assign(updates, completionUpdates(block, intent, targetStatus, normalizedStatus));
  if (present(intent.monitor_metadata)) {
    const monitor = requireJsonObject(intent.monitor_metadata, "monitor metadata");
    for (const field of MONITOR_FIELDS) if (Object.hasOwn(monitor, field)) updates[field] = monitor[field];
  }
  return {schema_version: TODO_FIELD_UPDATE_RESULT_SCHEMA, normalized_status: normalizedStatus,
    target_status: targetStatus, metadata_updates: updates};
}
