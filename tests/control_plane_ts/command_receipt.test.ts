import assert from "node:assert/strict";
import test from "node:test";
import type {AuthorityStore, AuthorityStoreCommit, AuthorityStoreCommitResult, AuthorityStoreReceiptResult} from "../../loopx/control_plane/coordination/authority_store.ts";
import {CoordinationCommandReceipt, commandReceiptResult} from "../../loopx/control_plane/coordination/command_receipt.ts";

const identity = {schema_version: "test_receipt_v0", operation_id: "original-operation",
  goal_id: "goal-a", request_sha256: "intent-digest"};
const original = {...identity, result: {changed: true, todo_id: "todo-a"}};
const found: AuthorityStoreReceiptResult = {status: "found", provider_revision: "historical-revision",
  cursor: "historical-cursor", receipts: [original]};
const commit: AuthorityStoreCommit = {operation_id: identity.operation_id,
  expected_provider_revision: "before", next_projection: {}, events: [], receipts: [original]};
const applied: AuthorityStoreCommitResult = {status: "applied", provider_revision: "historical-revision", cursor: "historical-cursor"};
const unavailable: AuthorityStoreReceiptResult = {status: "unavailable", reason_code: "disconnected", reason: "synthetic disconnect"};
const receipt = () => new CoordinationCommandReceipt({result_schema: "test_result_v0", identity,
  decode: commandReceiptResult, failure: (reason_code, reason) =>
    ({schema_version: "test_result_v0", status: "failed", changed: false, reason_code, reason})});
function store(result: AuthorityStoreCommitResult, readback: AuthorityStoreReceiptResult): AuthorityStore {
  return {storeIdentity: async () => {throw new Error("receipt recovery cannot inspect identity");},
    loadAuthority: async () => {throw new Error("receipt recovery cannot reinterpret the current head");},
    scanCommitted: async () => {throw new Error("receipt recovery cannot scan unrelated transactions");},
    commitAuthority: async () => result, readReceipt: async id => {
      assert.equal(id, identity.operation_id); return readback;
    }};
}

test("receipt identity rejects every cross-command, cross-goal and changed-intent alias", async () => {
  for (const field of Object.keys(identity)) {
    const result = await receipt().read(store(applied, {...found, receipts: [{...original, [field]: "different"}]}));
    assert.equal(result?.reason_code, "coordination_operation_identity_mismatch", field);
  }
  for (const receipts of [[], [original, original]]) {
    assert.equal((await receipt().read(store(applied, {...found, receipts})))?.reason_code,
      "coordination_operation_identity_mismatch");
  }
});

test("receipt read is a trust boundary: malformed result cannot become success or no-op", async () => {
  for (const result of [null, [], "invalid", {}, {changed: "false"}, {changed: 0}]) {
    const readback = {...found, receipts: [{...identity, result}]} as AuthorityStoreReceiptResult;
    const response = await receipt().read(store(applied, readback));
    assert.equal(response?.status, "failed");
    assert.equal(response?.reason_code, "invalid_coordination_command_receipt");
  }
});

test("historical no-op stays no-op on acceptance and never gains projection delivery", async () => {
  const readback = {...found, receipts: [{...identity, result: {changed: false}}]};
  const target = store(applied, readback);
  const result = await receipt().commit(target, commit);
  assert.equal(result.status, "no_change");
  assert.equal(result.projection_delivery, "not_required");
  assert.equal(result.changed, false);
  assert.equal((await receipt().read(target))?.changed, false);
  assert.equal((await receipt().read(target))?.status, "replayed");
});

test("pre-write receipt failure blocks planning and is not post-commit uncertainty", async () => {
  assert.equal((await receipt().read(store(applied, unavailable)))?.status, "unavailable");
  assert.equal(await receipt().read(store(applied, {status: "missing"})), null);
});

test("only an exact durable receipt resolves a lost or rejected commit response", async () => {
  const results: AuthorityStoreCommitResult[] = [applied,
    {status: "ambiguous", reason_code: "lost", reason: "response lost"},
    {status: "failed", reason_code: "rejected", reason: "write rejected"},
    {status: "conflict", conflict_kind: "operation_id_exists", current_provider_revision: "later", current_cursor: "later"}];
  for (const result of results) {
    const response = await receipt().commit(store(result, found), commit);
    assert.equal(response.status, result.status === "applied" ? "applied" : "recovered");
    assert.equal(response.provider_revision, found.provider_revision);
    assert.equal(response.cursor, found.cursor);
    assert.deepEqual(response.original_receipt, original);
  }
});

test("readback failure never erases a conclusive CAS conflict or rejection", async () => {
  for (const result of [
    {status: "conflict", conflict_kind: "provider_revision_mismatch", current_provider_revision: "other", current_cursor: "other"},
    {status: "failed", reason_code: "denied", reason: "write denied"},
  ] satisfies AuthorityStoreCommitResult[]) {
    const response = await receipt().commit(store(result, unavailable), commit);
    assert.equal(response.status, result.status);
    assert.equal(response.changed, false);
  }
});

test("successful response with absent durable receipt is a protocol violation", async () => {
  const response = await receipt().commit(store(applied, {status: "missing"}), commit);
  assert.equal(response.status, "failed");
  assert.equal(response.reason_code, "coordination_commit_readback_mismatch");
});

test("unresolved commit exposes same-operation recovery even when readback throws", async () => {
  const target = store(applied, unavailable);
  target.commitAuthority = async () => {throw new Error("synthetic post-commit response loss");};
  target.readReceipt = async () => {throw new Error("synthetic read failure");};
  const response = await receipt().commit(target, commit);
  assert.equal(response.status, "ambiguous");
  assert.deepEqual(response.recovery, {operation_id: identity.operation_id, retry_with_same_operation_id: true});
  assert.equal(response.changed, false);
  assert.equal(response.original_receipt, undefined);
});

test("a programmer error in a command decoder is not swallowed as corrupt storage", async () => {
  const invalid = new CoordinationCommandReceipt({result_schema: "test_result_v0", identity,
    decode() {throw new TypeError("decoder bug");},
    failure: (reason_code, reason) => ({schema_version: "test_result_v0", reason_code, reason})});
  await assert.rejects(invalid.read(store(applied, found)), /decoder bug/);
});

test("commit identity mismatch fails before the effect", async () => {
  let writes = 0;
  const target = store(applied, found);
  target.commitAuthority = async () => {writes++; return applied;};
  await assert.rejects(receipt().commit(target, {...commit, operation_id: "other"}), /identities differ/);
  assert.equal(writes, 0);
});
