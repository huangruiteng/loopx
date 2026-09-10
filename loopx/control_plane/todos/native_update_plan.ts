/** Bounded native planning edits. Compose the public rule owner in-process;
 * this plan never grants authority, reads storage, or emits a lease effect. */
import type { JsonObject } from "../effect_program.ts";
import { requireJsonObject } from "../runtime_decode.ts";
import { AuthorityStoreProtocolError } from "../coordination/authority_store_codec.ts";
import { compactPythonWhitespace } from "../coordination/todo_agents.ts";
import { normalizeTodoId } from "../work_items/task_lease_acquire.ts";
import { planPublicTodoUpdate, TODO_PUBLIC_UPDATE_REQUEST_SCHEMA } from "./public_update.ts";

const STRINGS = new Set(["status", "evidence", "reason", "resume_when", "unblocks_todo_id"]);
const BOOLEANS = new Set(["clear_resume_when", "no_followup"]);
const FIELDS = new Set([...STRINGS, ...BOOLEANS, "successor_todo_ids"]);

/** A separate intent namespace preserves the shipped text/note patch and its
 * historical receipt encoding. Raw field patches do not gain new authority. */
export function normalizeNativePlanningIntent(value: unknown): JsonObject {
  if (value === undefined || value === null) return {};
  const raw = requireJsonObject(value, "Todo planning intent");
  const intent: JsonObject = {};
  for (const [field, value] of Object.entries(raw)) {
    if (!FIELDS.has(field)) throw new AuthorityStoreProtocolError(`Todo planning update does not own ${field}`);
    if (value === null) continue;
    if (STRINGS.has(field)) {
      if (typeof value !== "string") throw new AuthorityStoreProtocolError(`${field} must be a string`);
      const text = compactPythonWhitespace(value);
      if (text) intent[field] = field === "unblocks_todo_id" ? normalizeTodoId(text, field) : text;
    } else if (BOOLEANS.has(field)) {
      if (typeof value !== "boolean") throw new AuthorityStoreProtocolError(`${field} must be a boolean`);
      if (field !== "clear_resume_when" || value) intent[field] = value;
    } else {
      if (!Array.isArray(value)) throw new AuthorityStoreProtocolError("successor_todo_ids must be an array");
      intent[field] = [...new Set(value.map(item => normalizeTodoId(item, "successor_todo_id")))];
    }
  }
  return intent;
}

export function planNativeTodoUpdate(todo: JsonObject, intent: JsonObject,
  head: JsonObject, actor: string | null, agents: readonly string[], updatedAt: string): JsonObject {
  if (todo.task_class === "continuous_monitor") {
    throw new AuthorityStoreProtocolError("native Monitor planning updates require the atomic monitor writer; text/note correction remains supported");
  }
  const planned = planPublicTodoUpdate({schema_version: TODO_PUBLIC_UPDATE_REQUEST_SCHEMA,
    todo, intent, updated_at: updatedAt,
    context: {goal_id: head.goal_id, role: todo.role, actor_agent_id: actor,
      registered_agents: [...agents], items: head.todos,
      monitor_observation: null, enforce_monitor_boundedness: true}});
  if (planned.target_status === "done" || planned.monitor_poll_transition != null) {
    throw new AuthorityStoreProtocolError("native planning update cannot complete work or commit a Monitor observation");
  }
  return requireJsonObject(planned.metadata_updates, "Todo planning metadata updates");
}
