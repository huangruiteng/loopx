import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import test from "node:test";
import { SqliteAuthorityStore } from "../../loopx/control_plane/coordination/sqlite_authority_store.ts";

test("unqualified SQLite runtime fails before creating authority files", async t => {
  const directory = await mkdtemp(join(tmpdir(), "sqlite-admission-"));
  t.after(() => rm(directory, {recursive: true, force: true}));
  let supportsFinalization = false;
  try {
    const {DatabaseSync} = createRequire(import.meta.url)("node:sqlite");
    const db = new DatabaseSync(":memory:");
    const statement = db.prepare("SELECT 1");
    db.close();
    try { statement.get(); }
    catch (error) { supportsFinalization = (error as NodeJS.ErrnoException).code === "ERR_INVALID_STATE"; }
  } catch { /* The optional native module may be unavailable on the core runtime. */ }
  const target = join(directory, "authority");
  const store = new SqliteAuthorityStore(target, "goal");
  const identity = await store.storeIdentity();
  if (supportsFinalization) {
    assert.equal(identity.status, "available");
    // All statements must have been finalized at the public method boundary.
    await rm(target, {recursive: true});
  } else {
    assert.equal(identity.status, "failed");
    if (identity.status === "failed") assert.match(identity.reason, /Node 22\.14/);
    assert.equal(existsSync(target), false);
    assert.equal((await store.commitAuthority({operation_id: "unsupported", expected_provider_revision: null,
      events: [], receipts: [], next_projection: {}})).status, "failed");
    assert.equal(existsSync(target), false);
  }
});
