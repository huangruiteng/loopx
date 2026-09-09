import assert from "node:assert/strict";
import test from "node:test";
import type { JsonObject } from "../../loopx/control_plane/effect_program.ts";
import { projectTodoResumePlanning, RESUME_PLANNING_REQUEST } from "../../loopx/control_plane/todos/resume_planning.ts";

function fact(id: string, overrides: JsonObject = {}): JsonObject {
  return {
    payload: { todo_id: id, index: 1, text: "Wait for work", role: "agent",
      task_class: "advancement_task", status: "deferred", resume_when: "capacity_available:compiler",
      resume_ready: false },
    id, status: "deferred", claim: null, excluded: [], done: false,
    resume: "capacity_available:compiler", ready: false, ready_truthy: false,
    priority: 1, index: 1, target_id: null, target_status: null,
    target_class: "advancement_task", ...overrides,
  };
}

function request(overrides: JsonObject = {}): JsonObject {
  return {
    schema_version: RESUME_PLANNING_REQUEST, agent_id: "agent-a", item_limit: 2,
    has_deferred_count: false, has_visible_deferred_count: false, deferred_count: null,
    available_capabilities: null,
    sources: { items: [], backlog_items: [], first_open_items: [], deferred_items: [],
      deferred_resume_candidates: [], resume_blocked_items: [], monitor_open_items: [],
      current_agent_claimed_monitor_items: [], claimed_monitor_open_items: [] },
    ...overrides,
  };
}

test("capacity evaluation and claim lanes use one snapshot without mutating it", () => {
  const input = request({ available_capabilities: ["compiler"] });
  (input.sources as JsonObject).items = [fact("todo_capacity", { claim: "agent-a" }),
    fact("todo_excluded", { excluded: ["agent-a"] })];
  const before = structuredClone(input);
  const result = projectTodoResumePlanning(input);
  const lanes = result.deferred_lanes as JsonObject;
  assert.equal(lanes.current_agent_deferred_resume_count, 1);
  assert.equal(lanes.executor_excluded_self_deferred_resume_count, 1);
  assert.equal(lanes.unclaimed_deferred_resume_count, 0);
  assert.equal((result.blocked_successor_items as unknown[]).length, 0);
  assert.deepEqual(input, before);
  input.available_capabilities = [];
  const unavailable = projectTodoResumePlanning(input).deferred_lanes as JsonObject;
  assert.equal(unavailable.current_agent_deferred_resume_count, 0);
});

test("a large wait source retains total counts independently from the display bound", () => {
  const input = request();
  const rows = Array.from({ length: 257 }, (_, i) => fact(`todo_wait_${i}`));
  (input.sources as JsonObject).deferred_items = rows;
  const result = projectTodoResumePlanning(input);
  const lanes = result.deferred_lanes as JsonObject;
  assert.equal(lanes.deferred_count, 257);
  assert.equal((lanes.deferred_items as unknown[]).length, 2);
  assert.equal((result.deferred_items as unknown[]).length, 257);
  assert.deepEqual(result.resume_blocked_lanes, {});
});

test("equal priority/index preserves source order, and zero display keeps counts", () => {
  const input = request({ item_limit: 0, has_deferred_count: true, deferred_count: 99 });
  (input.sources as JsonObject).items = [fact("todo_zed"), fact("todo_alpha")];
  const result = projectTodoResumePlanning(input);
  assert.deepEqual((result.deferred_items as JsonObject[]).map((row) => row.todo_id),
    ["todo_zed", "todo_alpha"]);
  assert.equal((result.deferred_lanes as JsonObject).deferred_count, 99);
  assert.deepEqual((result.deferred_lanes as JsonObject).deferred_items, []);
});

test("wire faults fail closed before selection instead of inventing readiness", () => {
  for (const override of [{ schema_version: "future" }, { item_limit: "2" },
    { has_deferred_count: null }, { available_capabilities: true }, { sources: {} }]) {
    assert.throws(() => projectTodoResumePlanning(request(override)));
  }
  for (const override of [{ ready: "false" }, { done: 0 }, { excluded: "agent-a" },
    { priority: null }, { payload: {} }]) {
    const input = request();
    (input.sources as JsonObject).items = [fact("todo_invalid", override)];
    assert.throws(() => projectTodoResumePlanning(input));
  }
});
