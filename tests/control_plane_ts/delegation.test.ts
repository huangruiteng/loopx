import test from "node:test";
import assert from "node:assert/strict";
import {delegationInventoryItem, delegationInventoryQuery, selectDelegationBinding, transitionDelegationObservation} from "../../loopx/control_plane/collaboration/delegation.ts";

const binding = {id: "review", agent_id: "reviewer", todo_id: "todo_review", workspace: "/fixture",
  requesters: ["coordinator", "analyst"], host_args: ["--host", "dsh"], timeout_seconds: 60, output_refs: ["output.json"]};
const params = {agent_id: "coordinator", binding_id: "review",
  config: {schema_version: "loopx_local_delegation_v0", bindings: [binding]}};

test("same explicit grant contract applies to a coordinator and an ordinary member", () => {
  assert.deepEqual(selectDelegationBinding(params), binding);
  assert.deepEqual(selectDelegationBinding({...params, agent_id: "analyst"}), binding);
  assert.throws(() => selectDelegationBinding({...params, agent_id: "unbound"}), /no delegation grant/);
  assert.throws(() => selectDelegationBinding({...params, agent_id: "reviewer"}), /no delegation grant/);
  assert.throws(() => selectDelegationBinding({...params, binding_id: "other"}), /unavailable/);
});

test("malformed operator binding fails before launch", () => {
  for (const patch of [{timeout_seconds: 0}, {timeout_seconds: 5000}, {output_refs: ["../secret"]},
    {output_refs: ["/secret"]}, {host_args: []}, {todo_id: null}]) {
    assert.throws(() => selectDelegationBinding({...params,
      config: {...params.config, bindings: [{...binding, ...patch}]}}));
  }
});

test("message receipt and model return do not imply accepted work", () => {
  assert.throws(() => transitionDelegationObservation({from: "prepared", to: "accepted"}), /transition/);
  assert.throws(() => transitionDelegationObservation({from: "turn_returned", to: "accepted"}), /canonical/);
  assert.throws(() => transitionDelegationObservation({from: "rejected", to: "running"}), /transition/);
  assert.deepEqual(transitionDelegationObservation({from: "turn_returned", to: "accepted",
    canonical_done: true, acceptance_ready: true, artifacts_current: true}), {status: "accepted"});
});

test("inventory paging is bounded and never interprets a missing result as accepted", () => {
  assert.deepEqual(delegationInventoryQuery({}), {limit: 20, cursor: null});
  for (const limit of [0, 51, true, "2"]) assert.throws(() => delegationInventoryQuery({limit}));
  assert.throws(() => delegationInventoryQuery({cursor: "../other"}));
  const record = {record_id: "a".repeat(64), operation_id: "review-1"};
  const observation = {operation_id: "review-1", request_id: "request", agent_id: "reviewer",
    todo_id: "todo_review", status: "accepted", worker_active: false, recovery_required: false,
    artifacts: [{ref: "output.json", sha256: "b".repeat(64), text: "private body"}]};
  const accepted = delegationInventoryItem({record, observation});
  assert.equal(accepted.status, "accepted");
  assert.equal(JSON.stringify(accepted).includes("private body"), false);
  assert.throws(() => delegationInventoryItem({record, observation: {...observation, artifacts: []}}));
  assert.throws(() => delegationInventoryItem({record, observation: {...observation, status: "done"}}));
  assert.throws(() => delegationInventoryItem({record, observation: {...observation, operation_id: "other"}}));
  const unavailable = delegationInventoryItem({record, observation: null});
  assert.equal(unavailable.status, "unavailable");
  assert.equal(unavailable.recovery_required, null);
  assert.equal(unavailable.artifacts, undefined);
});
