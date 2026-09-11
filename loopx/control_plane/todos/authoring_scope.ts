/** Public Todo authoring scope, not lifecycle permission or a commit receipt.
 * Explicit scope is intent; an author identity is only a default. */
import type { JsonObject } from "../effect_program.ts";
import { EffectRuntimeRequestError } from "../effect_runtime_errors.ts";
import { requireJsonObject } from "../runtime_decode.ts";
import { normalizeRegisteredTodoAgents, normalizeTodoAgent, stripPythonWhitespace } from "../coordination/todo_agents.ts";
import {
  normalizeTodoResumeWhen,
  TODO_RESUME_NORMALIZE_REQUEST_SCHEMA_VERSION,
  UNSUPPORTED_TODO_RESUME_CONDITION_MESSAGE,
} from "./resume_condition.ts";

export const TODO_AUTHORING_SCOPE_REQUEST_SCHEMA = "todo_authoring_scope_request_v0";
export const TODO_AUTHORING_SCOPE_RESULT_SCHEMA = "todo_authoring_scope_result_v0";
export const USER_TODO_TASK_CLASSES: ReadonlySet<string> = new Set(["user_action", "user_gate"]);
export const AGENT_TODO_TASK_CLASSES: ReadonlySet<string> = new Set(["advancement_task", "continuous_monitor", "blocker"]);
function fail(message: string): never { throw new EffectRuntimeRequestError(message); }
const INTENT_FIELDS = new Set(["task_class", "status", "actor_agent_id", "claimed_by", "bound_agent",
  "goal_bound", "blocks_agent", "global_gate", "clear_global_gate", "clear_blocks_agent", "excluded_agents",
  "task_repository", "task_domain", "capability_binding_ref", "resume_when", "clear_resume_when"]);

function string(value: unknown, field: string): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") return fail(`${field} must be a string or null`);
  return value;
}

function requireTaskClass(role: string, taskClass: string | null, blocks: unknown, global: unknown): void {
  if (role !== "user") {
    if (USER_TODO_TASK_CLASSES.has(taskClass ?? "")) fail("user_action and user_gate task_class are only valid for --role user");
    return;
  }
  const normalized = stripPythonWhitespace(taskClass ?? "");
  if (!USER_TODO_TASK_CLASSES.has(normalized)) fail("user todo requires explicit --task-class user_gate or user_action; " +
    "use user_gate for blocking owner/controller decisions and user_action for non-blocking user-visible todos");
  if (normalized === "user_action" && (blocks || global)) fail("user_action is non-blocking and cannot set blocks_agent or global_gate; " +
    "use --task-class user_gate for blocking decisions");
}

interface Scope {
  bound_agent: string | null;
  goal_bound: boolean | null;
  blocks_agent: string | null;
  global_gate: boolean | null;
}

export type UserTodoScopeConflict = "binding_conflict" | "gate_scope_conflict" |
  "global_binding_conflict" | "agent_binding_conflict" | "gate_scope_missing" | "binding_missing";

/** Check a fully resolved scope without inventing any authoring defaults.
 * Both public edits and materialized terminal successors consume this rule. */
export function userTodoScopeConflict(taskClass: string | null, scope: Scope,
  agentCount: number): UserTodoScopeConflict | null {
  const { bound_agent: bound, goal_bound: goal, blocks_agent: blocks, global_gate: global } = scope;
  if (bound && goal) return "binding_conflict";
  if (taskClass === "user_gate") {
    if (global && blocks) return "gate_scope_conflict";
    if (global && (bound || goal !== true)) return "global_binding_conflict";
    if (blocks && (goal || !bound || bound !== blocks)) return "agent_binding_conflict";
    if (agentCount > 1 && !blocks && global !== true) return "gate_scope_missing";
  }
  return agentCount > 1 && !bound && goal !== true ? "binding_missing" : null;
}

function validateScope(role: string, taskClass: string | null, scope: Scope, agentCount: number): void {
  const { bound_agent: bound, goal_bound: goal, blocks_agent: blocks, global_gate: global } = scope;
  if (role !== "user") {
    if (bound || goal) fail("bound_agent and goal_bound are only valid for user todos");
    return;
  }
  const conflict = userTodoScopeConflict(taskClass, scope, agentCount);
  if (conflict) fail({
    binding_conflict: "user todo cannot set both bound_agent and goal_bound=true; bind the continuation to one agent lane or explicitly to the whole goal",
    gate_scope_conflict: "user_gate cannot set both blocks_agent and global_gate=true; use blocks_agent for one registered agent or global_gate=true for a goal-wide gate",
    global_binding_conflict: "a goal-wide user_gate must use goal_bound=true and cannot bind its continuation to one agent",
    agent_binding_conflict: "an agent-scoped user_gate must bind to the same agent named by blocks_agent",
    binding_missing: "multi-agent user todo requires an explicit binding: pass --bound-agent <registered-agent> (or --agent-id <registered-agent> for authoring), or pass --goal-bound for an intentionally goal-wide user todo",
    gate_scope_missing: "multi-agent user_gate requires an explicit scope: pass --blocks-agent <registered-agent> (or --agent-id <registered-agent> for authoring) when the gate blocks one lane; only explicit --global-gate may block every registered agent. --goal-bound alone does not create a global gate",
  }[conflict]);
}

function planScope(command: string, role: string, taskClass: string | null, todo: JsonObject,
  intent: JsonObject, agents: string[], goalId: string): Scope {
  const registered = (field: string): string | null => {
    if (!intent[field]) return null;
    const value = normalizeTodoAgent(intent[field], field);
    if (!value || !agents.includes(value)) fail(`${field}='${value}' is not registered for goal '${goalId}'; registered_agents=${agents.join(", ")}`);
    return value;
  };
  const requestedBound = registered("bound_agent");
  const requestedBlocks = registered("blocks_agent");
  const actor = registered("actor_agent_id");
  if (requestedBound && intent.goal_bound) fail("todo update accepts either bound_agent or goal_bound, not both");
  if (requestedBlocks && intent.clear_blocks_agent) fail("todo update accepts either blocks_agent or clear_blocks_agent, not both");
  if (intent.global_gate && intent.clear_global_gate) fail("todo update accepts either global_gate or clear_global_gate, not both");
  if ((intent.global_gate || intent.clear_global_gate) && !(role === "user" && taskClass === "user_gate")) {
    fail(`${intent.clear_global_gate ? "clear_global_gate" : "global_gate"} is only valid for user_gate todos`);
  }
  if (role === "agent" && requestedBlocks) fail("blocks_agent is only valid for user gates; use excluded_agents for agent executor constraints");
  if (role === "user" && intent.claimed_by) fail("claimed_by is execution ownership for agent todos, not a user-todo binding; use --bound-agent or --goal-bound");
  for (const field of ["task_repository", "task_domain", "capability_binding_ref"]) {
    if (intent[field] && role !== "agent") fail(`${field} is only valid for agent todos`);
  }
  const creating = command === "create";
  let blocks = intent.clear_blocks_agent ? null : requestedBlocks || string(todo.blocks_agent, "blocks_agent");
  const global = intent.clear_global_gate ? null : intent.global_gate ? true : todo.global_gate as boolean | null ?? null;
  let bound = requestedBound || (intent.goal_bound ? null : string(todo.bound_agent, "bound_agent"));
  let goal = intent.goal_bound ? true : requestedBound ? false : todo.goal_bound as boolean | null ?? null;
  // Gate scope can determine continuation scope, but never overwrite a
  // contradictory explicit continuation. Only old/inferred binding is replaced.
  if (creating && role === "user" && taskClass === "user_gate" && !global && !blocks) blocks = actor;
  if (role === "user" && taskClass === "user_gate" && global) {
    if (requestedBound) fail("a goal-wide user_gate must use goal_bound=true and cannot bind its continuation to one agent");
    bound = null; goal = true;
  } else if (role === "user" && taskClass === "user_gate" && blocks) {
    if (intent.goal_bound || (requestedBound && requestedBound !== blocks)) fail("an agent-scoped user_gate must bind to the same agent named by blocks_agent");
    bound = blocks; goal = false;
  } else if (role === "user" && !bound && !goal) {
    bound = (creating ? actor : null) || (agents.length === 1 ? agents[0] : null);
  }
  if (!creating && role !== "user") {
    if (requestedBound || intent.goal_bound) fail("bound_agent and goal_bound are only valid for user todos");
    bound = null; goal = null;
  }
  return {bound_agent: bound, goal_bound: goal, blocks_agent: blocks, global_gate: global};
}

export function planTodoAuthoringScope(value: unknown): JsonObject {
  const request = requireJsonObject(value, "Todo authoring scope request");
  if (request.schema_version !== TODO_AUTHORING_SCOPE_REQUEST_SCHEMA) fail("Todo authoring scope schema mismatch");
  const command = string(request.command, "command");
  if (!["class", "create", "update"].includes(command ?? "")) fail("unsupported Todo authoring scope command");
  const role = string(request.role, "role");
  if (role !== "agent" && role !== "user") fail("todo role must be one of: user, agent");
  const intent = requireJsonObject(request.intent, "Todo authoring intent");
  for (const key of Object.keys(intent)) if (!INTENT_FIELDS.has(key)) fail(`Todo authoring scope does not own ${key}`);
  const todo = requireJsonObject(request.todo, "Todo authoring source");
  for (const object of [intent, todo]) for (const field of ["goal_bound", "global_gate", "clear_global_gate", "clear_blocks_agent", "clear_resume_when"]) {
    if (object[field] !== undefined && object[field] !== null && typeof object[field] !== "boolean") fail(`${field} must be a boolean or null`);
  }
  const taskClass = string(intent.task_class, "task_class") || string(todo.task_class, "task_class");
  if (command === "class") {
    requireTaskClass(role, taskClass, intent.blocks_agent, intent.global_gate);
    return {schema_version: TODO_AUTHORING_SCOPE_RESULT_SCHEMA};
  }
  const registeredAgents = request.registered_agents;
  if (!Array.isArray(registeredAgents)) fail("registered_agents must be an array");
  const agents = normalizeRegisteredTodoAgents(registeredAgents);
  const status = stripPythonWhitespace(string(intent.status, "status") ?? "").toLowerCase() || string(todo.status, "status") || "open";
  if (!["open", "done", "blocked", "deferred"].includes(status)) fail("todo status must be one of: open, done, blocked, deferred");
  if (command === "create" && status === "done") fail("todo add cannot create completed work; add it open and use `loopx todo complete`");
  if (command === "update" && role === "agent" && intent.status && status === "done") fail("agent todo completion must use complete_goal_todo " +
    "(CLI: `loopx todo complete`) so completion policy, successor, and no-follow-up contracts are enforced");
  const scope = planScope(command ?? "", role, taskClass, todo, intent, agents, string(request.goal_id, "goal_id") ?? "");
  const exclusions = intent.excluded_agents ?? todo.excluded_agents;
  if (role !== "agent" && Array.isArray(exclusions) && exclusions.length) fail("excluded_agents is only valid for agent todos; clear exclusions before moving this todo to a user role");
  // Completed history remains repairable; it does not create an active gate.
  if (status !== "done") {
    requireTaskClass(role, taskClass, scope.blocks_agent, scope.global_gate);
    validateScope(role, taskClass, scope, agents.length);
  }
  const resume = intent.resume_when ? normalizeTodoResumeWhen({schema_version: TODO_RESUME_NORMALIZE_REQUEST_SCHEMA_VERSION,
    resume_when: intent.resume_when}) : null;
  if (intent.resume_when && !resume) fail(UNSUPPORTED_TODO_RESUME_CONDITION_MESSAGE);
  if (resume && intent.clear_resume_when) fail("todo update accepts either resume_when or clear_resume_when, not both");
  const existingResume = todo.resume_when ? normalizeTodoResumeWhen({schema_version: TODO_RESUME_NORMALIZE_REQUEST_SCHEMA_VERSION,
    resume_when: todo.resume_when}) : null;
  const effectiveResume = intent.clear_resume_when ? null : resume || existingResume;
  if (status === "deferred" && !effectiveResume) fail("transition to deferred requires --resume-when with a supported condition");
  return {schema_version: TODO_AUTHORING_SCOPE_RESULT_SCHEMA, ...scope, task_class: taskClass,
    status, normalized_resume_when: resume, effective_resume_when: effectiveResume,
    clear_user_binding: role !== "user" && Boolean(todo.bound_agent || todo.goal_bound != null)};
}
