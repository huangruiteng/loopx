/** Dependent effects of an admitted User completion over one complete snapshot.
 * This plan grants no authority. Callers commit it with the source completion,
 * under their existing lock/CAS; replay returns the original transaction receipt.
 */
import type {JsonObject} from "../effect_program.ts";
import {requireJsonObject, requireStringLiteral} from "../runtime_decode.ts";
import {decisionScopeCovers} from "./decision_scope.ts";
import {normalizeTodoDecisionScope, normalizeTodoRequiredDecisionScopes} from "./decision_metadata.ts";

type DecisionOutcome = "approve" | "reject" | "cancel";
type ResumeState = "target_not_found" | "target_or_decision_scope_not_found" | "target_not_active" |
  "target_not_blocked" | "explicit_blocker_repair_required" | "other_user_blockers_active" |
  "decision_requirements_remaining" | "resumed" | "decision_rejected" | "decision_cancelled";
interface ResumeReceipt extends JsonObject { readonly state: ResumeState; }

export interface UserCompletionPlan extends JsonObject {
  readonly updates: JsonObject;
  readonly unblock_resume: ResumeReceipt | null;
  readonly decision_scope_resolution: JsonObject | null;
}
const inactive = (todo: JsonObject): boolean => todo.archive_state === "archive" ||
  todo.done === true || !["open", "blocked"].includes(String(todo.status || "open"));

export function planUserCompletion(
  source: JsonObject, todos: readonly JsonObject[], outcome: DecisionOutcome | null,
): UserCompletionPlan {
  const empty: UserCompletionPlan = {updates: {}, unblock_resume: null, decision_scope_resolution: null};
  if (source.role !== "user" || inactive(source) || typeof source.unblocks_todo_id !== "string") return empty;
  const gate = source.task_class === "user_gate";
  if (!(gate ? outcome !== null : source.task_class === "user_action")) return empty;
  const id = source.unblocks_todo_id;
  const base = {schema_version: "todo_unblock_resume_v0", source_todo_id: source.todo_id,
    target_todo_id: id, changed: false};
  const target = todos.find(row => row.todo_id === id && row.role === "agent" && row.archive_state !== "archive");
  const scope = gate ? normalizeTodoDecisionScope(source.decision_scope) : null;
  if (!target) return {...empty, unblock_resume: {...base,
    state: gate && outcome !== "approve" ? "target_or_decision_scope_not_found" : "target_not_found"}};
  // A late decision must not revive completed, archived, or deferred work.
  if (inactive(target)) return {...empty, unblock_resume: {...base, state: "target_not_active", status: target.status}};
  const status = String(target.status || "open");
  const requirements = normalizeTodoRequiredDecisionScopes(target.required_decision_scopes) ?? [];
  const rawOutcomes = target.decision_scope_outcomes ?? [];
  if (!Array.isArray(rawOutcomes)) throw new TypeError("decision_scope_outcomes must be an array");
  const outcomes = rawOutcomes.map(item => requireJsonObject(item, "decision scope outcome"));
  const updates: JsonObject = {};
  if (gate && outcome !== "approve") {
    if (!scope) return {...empty, unblock_resume: {...base, state: "target_or_decision_scope_not_found"}};
    const recorded = {schema_version: "todo_decision_scope_outcome_v0", outcome,
      decision_scope: scope, source_todo_id: source.todo_id};
    // Match the legacy codec: the newest decision replaces the same exact
    // scope in place, while independent scopes retain their order and evidence.
    const previous = outcomes.findIndex(item => decisionScopeCovers(scope, item.decision_scope) &&
      decisionScopeCovers(item.decision_scope, scope));
    const nextOutcomes = [...outcomes];
    if (previous < 0) nextOutcomes.push(recorded);
    else nextOutcomes[previous] = recorded;
    return {updates: {status: "blocked", decision_scope_outcomes: nextOutcomes},
      decision_scope_resolution: null, unblock_resume: {...base, changed: true, status: "blocked",
        state: outcome === "reject" ? "decision_rejected" : "decision_cancelled"}};
  }
  let resolution: JsonObject | null = null;
  const resolved = scope ? requirements.filter(item => decisionScopeCovers(scope, item)) : [];
  const remaining = requirements.filter(item => !resolved.includes(item));
  const remainingOutcomes = scope ? outcomes.filter(item => !decisionScopeCovers(scope, item.decision_scope)) : outcomes;
  if (resolved.length) {
    updates.required_decision_scopes = remaining;
    updates.decision_scope_outcomes = remainingOutcomes;
    resolution = {schema_version: "todo_decision_scope_resolution_v0", state: "resolved",
      source_todo_id: source.todo_id, target_todo_id: id, decision_scope: scope,
      resolved_required_decision_scopes: resolved, remaining_required_decision_scopes: remaining,
      changed: true, target_status: status};
  }
  const receipt = {...base, previous_status: status, status};
  const result = (state: ResumeState, extra: JsonObject = {}): UserCompletionPlan => ({updates,
    decision_scope_resolution: resolution, unblock_resume: {...receipt, state, ...extra}});
  if (status !== "blocked") return result("target_not_blocked");
  if (target.task_class === "blocker") return result("explicit_blocker_repair_required");
  const blockers = todos.filter(row => row.role === "user" && row.todo_id !== source.todo_id &&
    row.unblocks_todo_id === id && !inactive(row)).map(row => String(row.todo_id));
  if (blockers.length) return result("other_user_blockers_active", {remaining_user_blocker_todo_ids: [...new Set(blockers)].sort()});
  // Finishing one gate is not evidence that every independent requirement passed.
  if (remaining.length || remainingOutcomes.some(item => item.outcome === "reject" || item.outcome === "cancel")) return result("decision_requirements_remaining");
  updates.status = "open";
  updates.reason = `authorization satisfied by completed user todo ${source.todo_id}`;
  return result("resumed", {changed: true, status: "open", ...(target.claimed_by ? {claimed_by: target.claimed_by} : {})});
}

/** Legacy bridge: transport the whole decision once, not one RPC per scope. */
export function evaluateUserCompletion(value: unknown): UserCompletionPlan {
  const request = requireJsonObject(value, "user completion request");
  if (request.schema_version !== "todo_user_completion_request_v0" || !Array.isArray(request.todos)) {
    throw new TypeError("invalid user completion snapshot");
  }
  return planUserCompletion(requireJsonObject(request.source, "source"),
    request.todos.map(row => requireJsonObject(row, "todo")), request.decision_outcome == null ? null :
      requireStringLiteral(request.decision_outcome, ["approve", "reject", "cancel"] as const, "decision_outcome"));
}
