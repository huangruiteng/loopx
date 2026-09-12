import assert from "node:assert/strict";
import test from "node:test";
import type {AuthorityStoreConformanceFactory} from "./authority_store_conformance.ts";
import {productionScaleCoordinationFixture} from "./production_scale_coordination_fixture.ts";

/** Scan consumers must distinguish complete history from an invalid checkpoint.
 * Expectations follow the retained, contiguous journal contract, not a provider. */
export function registerAuthorityScanConformance(name: string, factory: AuthorityStoreConformanceFactory): void {
  test(`${name} scan contract: empty history cannot acknowledge a positive checkpoint`, async t => {
    const {store} = await factory(t);
    assert.deepEqual(await store.scanCommitted(null, 1),
      {status: "page", transactions: [], next_cursor: null, has_more: false});
    for (const cursor of ["1", "9007199254740993"]) {
      const result = await store.scanCommitted(cursor, 1);
      assert.equal(result.status, "failed", JSON.stringify(result));
      if (result.status === "failed") assert.equal(result.reason_code, "scan_cursor_out_of_range");
    }
    assert.deepEqual(await store.loadAuthority(), {status: "missing"});
  });

  test(`${name} scan contract: runtime cursor types never coerce into checkpoints`, async t => {
    const {store} = await factory(t);
    for (const cursor of [1, 1n, ["1"], {toString: () => "1"}, undefined, "0", "01", " 1"]) {
      const result = await store.scanCommitted(cursor as string, 1);
      assert.equal(result.status, "failed");
      if (result.status === "failed") assert.equal(result.reason_code, "invalid_scan_request");
    }
    assert.deepEqual(await store.loadAuthority(), {status: "missing"});
  });

  test(`${name} scan contract: complex historical pages retain exact identity and isolation`, async t => {
    const {store, contender} = await factory(t);
    const fixture = productionScaleCoordinationFixture("goal-scan-fixture");
    const original = structuredClone(fixture.projection);
    let revision: string | null = null;
    for (let index = 1; index <= 4; index++) {
      const result = await store.commitAuthority({expected_provider_revision: revision,
        operation_id: `history-${index}`, next_projection: {...original, authority_revision: index},
        events: [{kind: "projection_checkpoint", sequence: index}],
        receipts: [{operation_id: `history-${index}`, sequence: index, evidence: {valid: true}}]});
      assert.equal(result.status, "applied");
      if (result.status !== "applied") return;
      revision = result.provider_revision;
    }
    const before = await store.loadAuthority();
    let cursor: string | null = null;
    const seen: string[] = [];
    for (const limit of [1, 2, Number.MAX_SAFE_INTEGER]) {
      const page = await store.scanCommitted(cursor, limit);
      assert.equal(page.status, "page", JSON.stringify(page));
      if (page.status !== "page") return;
      for (const entry of page.transactions) {
        seen.push(entry.operation_id);
        assert.deepEqual(entry.projection.todos, original.todos);
        assert.deepEqual(entry.projection.leases, original.leases);
      }
      cursor = page.next_cursor;
      assert.equal(page.has_more, cursor !== "4");
      if (page.transactions.length) page.transactions[0]!.projection.todos = [];
    }
    assert.deepEqual(seen, ["history-1", "history-2", "history-3", "history-4"]);
    assert.deepEqual(await contender.loadAuthority(), before);
    assert.deepEqual(await store.scanCommitted("4", 1),
      {status: "page", transactions: [], next_cursor: "4", has_more: false});
    const receipt = await store.readReceipt("history-1");
    assert.equal(receipt.status, "found");
    if (receipt.status === "found") assert.equal(receipt.cursor, "1");
  });
}
