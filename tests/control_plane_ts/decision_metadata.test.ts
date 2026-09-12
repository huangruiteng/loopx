import assert from "node:assert/strict";
import test from "node:test";
import type {JsonObject} from "../../loopx/control_plane/effect_program.ts";
import {
  normalizeTodoDecisionScope,
  normalizeTodoRequiredDecisionScopes,
} from "../../loopx/control_plane/todos/decision_metadata.ts";
import {normalizeNativePlanningIntent} from "../../loopx/control_plane/todos/native_update_plan.ts";
import {
  planPublicTodoUpdate,
  TODO_PUBLIC_UPDATE_REQUEST_SCHEMA,
} from "../../loopx/control_plane/todos/public_update.ts";

const scope = {kind: "Direction", granularity: "Goal", scope_key: "release"};
const base = (role: "user" | "agent", task_class: string): JsonObject => ({
  todo_id: `todo_${role}_scope`, role, task_class, status: "open",
  text: "Decision metadata fixture", archive_state: "active",
  ...(role === "user" && task_class === "user_gate" ? {global_gate: true, goal_bound: true} : {}),
});

function plan(todo: JsonObject, intent: JsonObject): JsonObject {
  return planPublicTodoUpdate({schema_version: TODO_PUBLIC_UPDATE_REQUEST_SCHEMA,
    todo, intent, updated_at: "2026-09-13T00:00:00Z",
    context: {goal_id: "goal-scope", role: todo.role, actor_agent_id: "agent-a",
      registered_agents: ["agent-a", "agent-b"], items: [todo],
      enforce_monitor_boundedness: true}});
}

test("decision metadata normalizes compact and object forms without duplicate scopes", () => {
  assert.deepEqual(normalizeTodoDecisionScope(scope), {
    schema_version: "decision_scope_v0", kind: "direction", granularity: "goal", scope_key: "release",
  });
  assert.deepEqual(normalizeTodoDecisionScope("direction:goal:repo:release"), {
    schema_version: "decision_scope_v0", kind: "direction", granularity: "goal", scope_key: "repo:release",
  });
  assert.deepEqual(normalizeTodoRequiredDecisionScopes([
    "direction:goal:release", {kind: "DIRECTION", granularity: "GOAL", scope_key: "release"},
    {kind: "write_scope", granularity: "action", scope_key: "publish"},
  ]), [
    {schema_version: "decision_scope_v0", kind: "direction", granularity: "goal", scope_key: "release"},
    {schema_version: "decision_scope_v0", kind: "write_scope", granularity: "action", scope_key: "publish"},
  ]);
});

for (const [label, value] of [
  ["unknown kind", {kind: "secret", granularity: "goal", scope_key: "release"}],
  ["invalid key", {kind: "direction", granularity: "goal", scope_key: "../release"}],
  ["unknown field", {kind: "direction", granularity: "goal", scope_key: "release", reason_summary: "owner"}],
  ["wrong schema", {schema_version: "decision_scope_v1", kind: "direction", granularity: "goal", scope_key: "release"}],
  ["invalid list member", ["direction:goal:release", "not-a-scope"]],
] as const) {
  test(`invalid decision metadata fails closed: ${label}`, () => {
    assert.throws(() => Array.isArray(value)
      ? normalizeTodoRequiredDecisionScopes(value)
      : normalizeTodoDecisionScope(value));
  });
}

test("user gates own decision_scope and agent work owns required_decision_scopes", () => {
  const userGate = base("user", "user_gate");
  const gate = plan(userGate, {decision_scope: scope});
  assert.deepEqual((gate.metadata_updates as JsonObject).decision_scope, {
    schema_version: "decision_scope_v0", kind: "direction", granularity: "goal", scope_key: "release",
  });

  const agent = base("agent", "advancement_task");
  const requirement = plan(agent, {required_decision_scopes: [scope]});
  assert.deepEqual((requirement.metadata_updates as JsonObject).required_decision_scopes, [{
    schema_version: "decision_scope_v0", kind: "direction", granularity: "goal", scope_key: "release",
  }]);
  assert.throws(() => plan(agent, {decision_scope: scope}), /only valid for user_gate/);
  assert.throws(() => plan(userGate, {required_decision_scopes: [scope]}), /only valid for agent/);
});

test("explicit empty required scopes clear a stale dependency without touching outcomes", () => {
  const agent = base("agent", "advancement_task");
  agent.required_decision_scopes = [{schema_version: "decision_scope_v0", ...scope}];
  const result = plan(agent, {required_decision_scopes: []});
  const updates = result.metadata_updates as JsonObject;
  assert.deepEqual(updates.required_decision_scopes, []);
  assert.equal(Object.hasOwn(updates, "decision_outcome"), false);
  assert.equal(Object.hasOwn(updates, "decision_scope_outcomes"), false);
});

test("role repair may clear an invalid retained decision_scope without granting one", () => {
  const agent = base("agent", "advancement_task");
  agent.decision_scope = {schema_version: "decision_scope_v0", ...scope};
  const result = plan(agent, {decision_scope: null});
  const updates = result.metadata_updates as JsonObject;
  assert.equal(updates.decision_scope, null);
});

test("decision outcomes remain effect-owned and cannot cross the native planning boundary", () => {
  assert.throws(() => normalizeNativePlanningIntent({decision_outcome: "approve"}), /does not own/);
  assert.throws(() => normalizeNativePlanningIntent({decision_scope_outcomes: []}), /does not own/);
});
