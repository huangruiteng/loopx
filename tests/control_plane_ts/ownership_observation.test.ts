import assert from "node:assert/strict";
import test from "node:test";
import {projectOwnershipObservation, OWNERSHIP_OBSERVATION_SCHEMA} from "../../loopx/control_plane/coordination/ownership_observation.ts";
const at = "2026-09-13T00:00:00Z";
const request = {schema_version: OWNERSHIP_OBSERVATION_SCHEMA, observed_at: at,
  todos: [{todo_id: "todo-a", claimed_by: "agent-a"}], explicit_entries: null, lease_rows: []};
const lease = {schema_version: "task_lease_v0", todo_id: "todo-a", owner: "agent-b",
  status: "active", expires_at: "2027-01-01T00:00:00Z", version: 2};

test("explicit empty differs from absent observation; source inputs are not mutated", () => {
  assert.equal((projectOwnershipObservation(request).entries as unknown[]).length, 1);
  const input = {...request, explicit_entries: []};
  assert.deepEqual(projectOwnershipObservation(input).entries, []);
  assert.deepEqual(input.explicit_entries, []);
});
test("explicit entries keep only the public ownership display fields", () => {
  const result = projectOwnershipObservation({...request, explicit_entries: [{
    todo_id: "todo-a", owner_agent: "agent-a", status: "hard_lease", lease_epoch: 2,
    write_scopes: ["private/**"], idempotency_key: "PRIVATE_OPERATION_KEY", private_backend: "PRIVATE_BACKEND",
  }]});
  assert.deepEqual(result.entries, [{todo_id: "todo-a", owner_agent: "agent-a", status: "hard_lease", lease_epoch: 2}]);
});
for (const patch of [{expires_at: "invalid"}, {schema_version: "unknown"}, {lease_epoch: true}, {todo_id: "wrong-id"}]) {
  test(`invalid lease observation is visible and never crashes the channel: ${JSON.stringify(patch)}`, () => {
    const result = projectOwnershipObservation({...request, lease_rows: [{todo_id: "todo-a", lease: {...lease, ...patch}}]});
    assert.deepEqual((result.entries as unknown[])[1], {todo_id: "todo-a", status: "hard_lease_unreadable", reason: "corrupt_lease"});
  });
}
test("all leases use the same observation time; exact expiry is expired", () => {
  assert.equal((projectOwnershipObservation({...request, lease_rows: [{todo_id: "todo-a", lease: {...lease, expires_at: at}}]}).entries as unknown[]).length, 1);
  assert.throws(() => projectOwnershipObservation({...request, observed_at: "invalid"}));
});
