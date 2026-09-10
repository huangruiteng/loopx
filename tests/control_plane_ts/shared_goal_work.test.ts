import assert from "node:assert/strict";
import test from "node:test";
import { sharedGoalWorkFacts } from "../../loopx/control_plane/goals/shared_goal_work.ts";

const at = "2026-09-09T12:00:00Z";
const item = (todo_id: string, extra = {}) => ({todo_id, status: "open", task_class: "advancement_task", ...extra});

test("alignment selection respects exclusions without narrowing amendment impact", () => {
  const result = sharedGoalWorkFacts([
    item("todo_own", {claimed_by: "agent-a"}), item("todo_free"),
    item("todo_excluded", {excluded_agents: ["agent-a"]}),
    item("todo_peer", {claimed_by: "agent-b"}),
    item("todo_own_excluded", {claimed_by: "agent-a", excluded_agents: ["agent-a"]}),
  ], "agent-a", at);
  assert.deepEqual(result.frontier_counts, {current_agent_claimed_advancement_count: 1,
    unclaimed_advancement_count: 1, other_agent_claimed_advancement_count: 1});
  assert.deepEqual(result.unclaimed_eligible, [{todo_id: "todo_free", task_class: "advancement_task"}]);
  assert.equal((result.goal_todo_inventory as unknown[]).length, 5);
});

test("closed, archived and unsatisfied waits cannot reenter the open inventory", () => {
  const result = sharedGoalWorkFacts([
    item("todo_done", {done: true}), item("todo_archive", {archive_state: "archive"}),
    item("todo_blocked", {status: "blocked"}), item("todo_deferred", {status: "deferred", resume_ready: true}),
    item("todo_wait", {resume_when: "todo_done:todo_target", resume_ready: false}),
    item("todo_ready", {resume_when: "todo_done:todo_target", resume_ready: true}),
    item("todo_monitor", {task_class: "continuous_monitor"}),
  ], "agent-a", at);
  assert.deepEqual((result.goal_todo_inventory as {todo_id: string}[]).map((x) => x.todo_id), ["todo_ready", "todo_monitor"]);
  assert.deepEqual(result.unclaimed_eligible, [{todo_id: "todo_ready", task_class: "advancement_task"}]);
});

test("lease facts use the existing typed epoch and activity rules only for selected claims", () => {
  const lease = {schema_version: "task_lease_v0", status: "active", expires_at: "2099-01-01T00:00:00Z",
    owner: "agent-b", lease_epoch: 3};
  const result = sharedGoalWorkFacts([item("todo_own", {claimed_by: "agent-a", lease}),
    item("todo_peer", {claimed_by: "agent-b", lease: {...lease, lease_epoch: 0}})], "agent-a", at);
  assert.deepEqual(result.claims, [{todo_id: "todo_own", claimed_by: "agent-a", lease_epoch: 3, lease_owner: "agent-b"}]);
  for (const bad of [{lease_epoch: true}, {lease_epoch: 0}, {expires_at: "broken"}, {owner: ""}]) {
    assert.throws(() => sharedGoalWorkFacts([item("todo_own", {claimed_by: "agent-a", lease: {...lease, ...bad}})], "agent-a", at));
  }
  const expired = sharedGoalWorkFacts([item("todo_own", {claimed_by: "agent-a",
    lease: {...lease, expires_at: at}})], "agent-a", at);
  assert.deepEqual(expired.claims, [{todo_id: "todo_own", claimed_by: "agent-a", lease_epoch: null, lease_owner: null}]);
});

test("full input is not limited by display budgets and contradictory records fail closed", () => {
  assert.equal((sharedGoalWorkFacts(Array.from({length: 400}, (_, i) => item(`todo_item_${i}`)), "agent-a", at)
    .unclaimed_eligible as unknown[]).length, 400);
  assert.throws(() => sharedGoalWorkFacts([item("todo_same"), item("todo_same")], "agent-a", at), /duplicate/);
  assert.throws(() => sharedGoalWorkFacts([item("todo_bad", {done: "false"})], "agent-a", at), /boolean/);
  assert.throws(() => sharedGoalWorkFacts([item("todo_bad", {status: "invented"})], "agent-a", at), /status/);
  assert.throws(() => sharedGoalWorkFacts([], "agent-a", "not a date"), /observed_at/);
});
