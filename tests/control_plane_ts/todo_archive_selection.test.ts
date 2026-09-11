import assert from "node:assert/strict";
import test from "node:test";

import {
  COORDINATION_TODO_ARCHIVE_SELECTION_SCHEMA,
  evaluateCoordinationTodoArchiveSelection,
  selectCoordinationTodoArchive,
} from "../../loopx/control_plane/coordination/todo_archive_selection.ts";

function doneTodo(todoId: string, overrides: Record<string, unknown> = {}) {
  return {
    todo_id: todoId,
    role: "agent",
    status: "done",
    archive_state: "active",
    ...overrides,
  };
}

test("archive selection preserves imported order before native timestamp fallback", () => {
  const selected = selectCoordinationTodoArchive({
    role: "agent",
    max_active_done: 2,
    todos: [
      doneTodo("native-new", {completed_at: "2026-09-08T03:00:00Z"}),
      doneTodo("imported-new", {index: 2}),
      doneTodo("native-old-z", {completed_at: "2026-09-08T01:00:00Z"}),
      doneTodo("imported-old", {index: 1}),
      doneTodo("native-old-a", {completed_at: "2026-09-08T01:00:00Z"}),
    ],
  });

  assert.equal(selected.schema_version, COORDINATION_TODO_ARCHIVE_SELECTION_SCHEMA);
  assert.deepEqual(selected.moved_todo_ids, [
    "imported-old",
    "imported-new",
    "native-old-a",
  ]);
  assert.equal(selected.active_done_before, 5);
  assert.equal(selected.active_done_after, 2);
});

test("archive selection retains standing user decision receipts", () => {
  const selected = selectCoordinationTodoArchive({
    role: "user",
    max_active_done: 0,
    todos: [
      doneTodo("ordinary", {role: "user", index: 1}),
      doneTodo("standing", {
        role: "user",
        index: 2,
        task_class: "user_gate",
        decision_scope: {kind: "write_scope", granularity: "goal", scope_key: "release"},
        decision_outcome: "approve",
        global_gate: true,
      }),
      doneTodo("scoped", {
        role: "user",
        index: 3,
        task_class: "user_gate",
        decision_scope: {kind: "write_scope", granularity: "goal", scope_key: "one-task"},
        decision_outcome: "approve",
        global_gate: true,
        unblocks_todo_id: "todo-a",
      }),
    ],
  });

  assert.deepEqual(selected.moved_todo_ids, ["ordinary", "scoped"]);
  assert.equal(selected.retained_standing_decision_count, 1);
  assert.equal(selected.active_done_after, 1);
});

test("archive selection ignores nonmatching and nonterminal records without pressure", () => {
  const selected = selectCoordinationTodoArchive({
    role: "agent",
    max_active_done: 1,
    todos: [
      doneTodo("only-complete"),
      doneTodo("already-archived", {archive_state: "archive"}),
      doneTodo("open", {status: "open"}),
      doneTodo("user", {role: "user"}),
    ],
  });

  assert.deepEqual(selected.moved_todo_ids, []);
  assert.equal(selected.active_done_before, 1);
  assert.equal(selected.active_done_after, 1);
});

test("archive wire rejects invalid limits, roles, and duplicate completed ids", () => {
  for (const max_active_done of [true, "1", 1.5, -1]) {
    assert.throws(() => evaluateCoordinationTodoArchiveSelection({
      role: "agent",
      max_active_done,
      todos: [],
    }), /max_active_done.*safe integer/);
  }
  assert.throws(() => evaluateCoordinationTodoArchiveSelection({
    role: "observer",
    max_active_done: 0,
    todos: [],
  }), /archive role/);
  assert.throws(() => evaluateCoordinationTodoArchiveSelection({
    role: "agent",
    max_active_done: 0,
    todos: [doneTodo("duplicate"), doneTodo("duplicate")],
  }), /must be unique/);
});
