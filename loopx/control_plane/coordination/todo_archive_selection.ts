import type { JsonObject } from "../effect_program.ts";
import {isStandingDecisionReceipt} from "../todos/standing_decision.ts";
import {
  authorityUnicodeCompare,
  canonicalAuthorityObject,
  requireAuthorityStoreId,
} from "./authority_store_codec.ts";

export const COORDINATION_TODO_ARCHIVE_SELECTION_SCHEMA =
  "loopx_coordination_todo_archive_selection_v0";

const TODO_ROLES = ["agent", "user"] as const;

export type CoordinationTodoArchiveRole = typeof TODO_ROLES[number];

export interface CoordinationTodoArchiveSelectionInput {
  readonly role: CoordinationTodoArchiveRole;
  readonly max_active_done: number;
  readonly todos: readonly JsonObject[];
}

export type CoordinationTodoArchiveSelectionResult = JsonObject & {
  readonly schema_version: typeof COORDINATION_TODO_ARCHIVE_SELECTION_SCHEMA;
  readonly role: CoordinationTodoArchiveRole;
  readonly active_done_before: number;
  readonly active_done_after: number;
  readonly max_active_done: number;
  readonly moved_count: number;
  readonly moved_todo_ids: readonly string[];
  readonly retained_standing_decision_count: number;
};

function archiveRole(value: unknown): CoordinationTodoArchiveRole {
  if (value !== "agent" && value !== "user") {
    throw new TypeError("archive role must be one of: agent, user");
  }
  return value;
}

function archiveLimit(value: unknown): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) {
    throw new TypeError("max_active_done must be a non-negative safe integer");
  }
  return Number(value);
}

function archiveOrder(left: JsonObject, right: JsonObject): number {
  const leftIndex = Number.isSafeInteger(left.index) && Number(left.index) >= 0
    ? Number(left.index) : null;
  const rightIndex = Number.isSafeInteger(right.index) && Number(right.index) >= 0
    ? Number(right.index) : null;
  if (leftIndex !== null || rightIndex !== null) {
    if (leftIndex === null) return 1;
    if (rightIndex === null) return -1;
    if (leftIndex !== rightIndex) return leftIndex - rightIndex;
  }
  const leftTime = typeof left.completed_at === "string"
    ? left.completed_at : typeof left.updated_at === "string" ? left.updated_at : "";
  const rightTime = typeof right.completed_at === "string"
    ? right.completed_at : typeof right.updated_at === "string" ? right.updated_at : "";
  if (leftTime !== rightTime) return authorityUnicodeCompare(leftTime, rightTime);
  return authorityUnicodeCompare(String(left.todo_id), String(right.todo_id));
}

/** Select completed Todo ids without owning storage or applying mutations. */
export function selectCoordinationTodoArchive(
  input: CoordinationTodoArchiveSelectionInput,
): CoordinationTodoArchiveSelectionResult {
  const role = archiveRole(input.role);
  const maxActiveDone = archiveLimit(input.max_active_done);
  const completed = input.todos
    .filter((todo) => todo.role === role && todo.archive_state === "active" &&
      todo.status === "done")
    .map((todo) => ({
      ...todo,
      todo_id: requireAuthorityStoreId(todo.todo_id, "completed Todo id"),
    }))
    .sort(archiveOrder);
  const completedIds = completed.map((todo) => String(todo.todo_id));
  if (new Set(completedIds).size !== completedIds.length) {
    throw new TypeError("completed Todo ids must be unique");
  }
  const retainedStanding = role === "user"
    ? completed.filter(isStandingDecisionReceipt) : [];
  const retainedIds = new Set(retainedStanding.map((todo) => String(todo.todo_id)));
  const movable = completed.filter((todo) => !retainedIds.has(String(todo.todo_id)));
  const moveCount = Math.min(
    movable.length,
    Math.max(0, completed.length - maxActiveDone),
  );
  const movedTodoIds = movable.slice(0, moveCount).map((todo) => String(todo.todo_id));
  return {
    schema_version: COORDINATION_TODO_ARCHIVE_SELECTION_SCHEMA,
    role,
    active_done_before: completed.length,
    active_done_after: completed.length - movedTodoIds.length,
    max_active_done: maxActiveDone,
    moved_count: movedTodoIds.length,
    moved_todo_ids: movedTodoIds,
    retained_standing_decision_count: retainedStanding.length,
  };
}

/** Strict wire decoder used by the transitional Python compatibility writer. */
export function evaluateCoordinationTodoArchiveSelection(
  value: JsonObject,
): CoordinationTodoArchiveSelectionResult {
  const request = canonicalAuthorityObject(value, "Todo archive selection request");
  if (!Array.isArray(request.todos)) {
    throw new TypeError("todos must be an array");
  }
  return selectCoordinationTodoArchive({
    role: archiveRole(request.role),
    max_active_done: archiveLimit(request.max_active_done),
    todos: request.todos.map((todo, index) =>
      canonicalAuthorityObject(todo, `todos[${index}]`)),
  });
}
