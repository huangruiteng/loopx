import assert from "node:assert/strict";
import test from "node:test";
import { decodeAuthorityTransaction, transactionForRevision } from "../../loopx/control_plane/coordination/authority_store_transactions.ts";

test("all providers share one strict transaction decoder", () => {
  const tx = decodeAuthorityTransaction({cursor:"1", provider_revision:"file:1:x", operation_id:"op", events:[], projection:{}, receipts:[]});
  assert.deepEqual(transactionForRevision(tx), {cursor:"1", operation_id:"op", events:[], projection:{}, receipts:[]});
  assert.throws(() => decodeAuthorityTransaction({...tx, receipts: "not-an-array"}), /transaction receipts/);
  assert.throws(() => decodeAuthorityTransaction({...tx, extra: true}), /committed transaction is invalid/);
});
