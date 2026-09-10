import assert from "node:assert/strict";
import test from "node:test";
import type { JsonObject } from "../../loopx/control_plane/effect_program.ts";
import { planPublicTodoUpdate, TODO_PUBLIC_UPDATE_REQUEST_SCHEMA } from "../../loopx/control_plane/todos/public_update.ts";
import { productionScaleCoordinationFixture } from "./production_scale_coordination_fixture.ts";

const todo = {todo_id: "todo_waiting", role: "agent", status: "open", task_class: "advancement_task",
  claimed_by: "agent-a", resume_when: "monitor_changed:todo_monitor", resume_monitor_generation: 3,
  successor_todo_ids: ["todo_successor"]};
const monitor = {todo_id: "todo_monitor", role: "agent", status: "open", task_class: "continuous_monitor",
  material_change_generation: 3};
const successor = {todo_id: "todo_successor", role: "agent", status: "open", task_class: "advancement_task"};
function plan(intent: JsonObject = {}, source: JsonObject = todo, extra: JsonObject = {}) {
  return planPublicTodoUpdate({schema_version: TODO_PUBLIC_UPDATE_REQUEST_SCHEMA, todo: source,
    intent, updated_at: "2030-01-01T00:00:00Z", context: {goal_id: "goal-a", role: source.role,
      actor_agent_id: "agent-a", registered_agents: ["agent-a", "agent-b"],
      enforce_monitor_boundedness: true, items: [source, monitor, successor], ...extra}});
}

test("partial topology edits validate the effective retained wait", () => {
  for (const edit of [{successor_todo_ids: []}, {status: "blocked"}, {task_class: "continuous_monitor"}]) {
    assert.throws(() => plan(edit), /external-wait/);
  }
  const clear = plan({clear_resume_when: true, successor_todo_ids: []});
  const updates = clear.metadata_updates as JsonObject;
  assert.equal(updates.resume_when, null);
  assert.equal(updates.resume_monitor_generation, null);
  assert.deepEqual(updates.successor_todo_ids, []);
});

test("same-condition retry keeps the baseline; ordinary copy does not rearm", () => {
  const copy = plan({note: "Clarified"}, todo, {items: [todo, {...monitor, material_change_generation: 4}, successor]});
  assert.equal(copy.external_wait_transition, undefined);
  assert.equal((copy.metadata_updates as JsonObject).resume_monitor_generation, undefined);
  const retry = plan({resume_when: todo.resume_when});
  assert.equal((retry.metadata_updates as JsonObject).resume_monitor_generation, 3);
  assert.equal((retry.external_wait_transition as JsonObject).state, "already_waiting");
  assert.throws(() => plan({resume_when: todo.resume_when}, todo,
    {items: [todo, {...monitor, material_change_generation: 4}, successor]}), /clear the satisfied/);
  assert.equal(todo.resume_monitor_generation, 3);
});

test("deferred Todo and ordinary capacity/PR conditions retain their distinct contracts", () => {
  const deferred = plan({status: "deferred", resume_when: "todo_done:todo_successor", successor_todo_ids: []});
  assert.equal(deferred.external_wait_transition, undefined);
  assert.equal((deferred.metadata_updates as JsonObject).resume_monitor_generation, null);
  for (const condition of ["capacity_available:network", "pr_merged:owner/repo#12"]) {
    assert.equal(plan({resume_when: condition}).external_wait_transition, undefined);
  }
  assert.throws(() => plan({resume_when: "monitor_changed:todo_waiting"}), /itself/);
  assert.throws(() => plan({resume_when: "monitor_changed:todo_absent"}), /absent/);
});

test("public scope and fields agree without inventing a global gate", () => {
  const gate = {todo_id: "todo_gate", role: "user", task_class: "user_gate", status: "open",
    bound_agent: "agent-a", blocks_agent: "agent-a", goal_bound: false, global_gate: false};
  const updates = plan({blocks_agent: "agent-b"}, gate).metadata_updates as JsonObject;
  assert.equal(updates.bound_agent, "agent-b");
  assert.equal(updates.blocks_agent, "agent-b");
  assert.equal(updates.global_gate, undefined);
  assert.throws(() => plan({goal_bound: true}, gate), /same agent/);
  assert.throws(() => plan({status: "done"}), /complete_goal_todo/);
});

test("monitor observations use the same effective task scope and cannot be raw-state overrides", () => {
  const observation = {generated_at: "2030-01-01T00:00:00Z", material_change: true,
    result_hash: "changed", monitor_effect_id: "effect-a"};
  const result = plan({}, {...monitor, watch_only: true}, {monitor_observation: observation});
  assert.equal((result.metadata_updates as JsonObject).material_change_generation, "4");
  assert.throws(() => plan({task_class: "advancement_task"}, {...monitor, watch_only: true},
    {monitor_observation: observation}), /monitor schedule metadata/);
  assert.throws(() => plan({monitor_metadata: {result_hash: "forged"}}, {...monitor, watch_only: true},
    {monitor_observation: observation}), /cannot be combined/);
});

test("complete production-scale snapshot stays immutable and is not display-capped", () => {
  const fixture = productionScaleCoordinationFixture("goal-a");
  const snapshot = structuredClone(fixture);
  const records = fixture.projection.todos as JsonObject[];
  const result = plan({resume_when: todo.resume_when}, todo,
    {items: [...records, todo, monitor, successor]});
  assert.equal((result.metadata_updates as JsonObject).resume_monitor_generation, 3);
  assert.deepEqual(fixture, snapshot);
});
