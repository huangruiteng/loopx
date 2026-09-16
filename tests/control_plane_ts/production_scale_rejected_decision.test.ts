import assert from "node:assert/strict";
import test from "node:test";

import type {JsonObject} from "../../loopx/control_plane/effect_program.ts";
import {
  isStandingDecisionReceipt,
  projectStandingDecisions,
} from "../../loopx/control_plane/todos/standing_decision.ts";
import {
  PRODUCTION_SCALE_REJECTED_DECISION_COUNT,
  productionScaleCoordinationFixture,
} from "./production_scale_coordination_fixture.ts";

function standingEntries(todos: readonly JsonObject[]): JsonObject[] {
  const standing = projectStandingDecisions(todos);
  return (standing?.entries ?? []) as JsonObject[];
}

function rejectedTodos(todos: readonly JsonObject[]): JsonObject[] {
  return todos.filter(todo => todo.decision_outcome === "reject");
}

test("production-scale rejections are standing receipts that stay inactive", () => {
  const fixture = productionScaleCoordinationFixture("fixture-goal");
  const todos = fixture.projection.todos as JsonObject[];
  const rejected = rejectedTodos(todos);
  assert.equal(rejected.length, PRODUCTION_SCALE_REJECTED_DECISION_COUNT);
  assert.equal(rejected.length > 0, true, "the fixture must carry a recorded rejection");
  for (const todo of rejected) {
    assert.equal(isStandingDecisionReceipt(todo), true,
      "an explicit rejection is a decision, not an absent one");
    assert.equal(todo.status, "done");
    assert.equal(todo.global_gate, true);
  }
  const entries = standingEntries(todos);
  const rejections = entries.filter(entry => entry.outcome === "reject");
  assert.equal(rejections.length, fixture.expected_inactive_standing_decision_count);
  for (const entry of rejections) {
    assert.equal(entry.active, false, "a rejection must never read as an approval");
  }
});

test("only an explicit approval activates a production-scale decision scope", () => {
  const fixture = productionScaleCoordinationFixture("fixture-goal");
  const todos = fixture.projection.todos as JsonObject[];
  const before = standingEntries(todos);
  const approved = before.filter(entry => entry.active === true).length;
  const approvedTodo = todos
    .filter(todo => todo.decision_outcome === "approve" && isStandingDecisionReceipt(todo))
    .sort((left, right) => String(left.completed_at).localeCompare(String(right.completed_at)))
    .at(-1)!;
  // Mutation: the newest rejection decides the scope once its outcome changes.
  const newest = rejectedTodos(todos)
    .sort((left, right) => String(left.completed_at).localeCompare(String(right.completed_at)))
    .at(-1)!;
  const mutated = todos.map(todo => todo === newest
    ? {...todo, decision_outcome: "approve"} : todo);
  const after = standingEntries(mutated);
  assert.equal(after.filter(entry => entry.active === true).length, approved + 1);
  assert.equal(after.some(entry => entry.outcome === "reject" && entry.active === true), false);
  // The untouched approval is still the same receipt.
  assert.equal(after.some(entry => entry.source_todo_id === approvedTodo.todo_id), true);
});

test("a rejection without its typed decision scope leaves no standing entry", () => {
  const fixture = productionScaleCoordinationFixture("fixture-goal");
  const todos = fixture.projection.todos as JsonObject[];
  const stripped = todos.map(todo => todo.decision_outcome === "reject"
    ? {...todo, decision_scope: undefined} : todo);
  for (const todo of stripped) {
    if (todo.decision_outcome === "reject") {
      assert.equal(isStandingDecisionReceipt(todo), false,
        "decision identity comes from the typed scope, never from prose");
    }
  }
  assert.equal(standingEntries(stripped).some(entry => entry.outcome === "reject"), false);
  assert.equal(standingEntries(stripped).length,
    standingEntries(todos).length - fixture.expected_inactive_standing_decision_count);
});
