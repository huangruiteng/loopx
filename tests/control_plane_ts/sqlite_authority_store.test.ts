import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import test from "node:test";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { SqliteAuthorityStore } from "../../loopx/control_plane/coordination/sqlite_authority_store.ts";
import { authorityStoreCommitFixture, registerAuthorityStoreConformance } from "./authority_store_conformance.ts";

async function fixture(t: test.TestContext) {
  const directory = await mkdtemp(join(tmpdir(), "sqlite-authority-"));
  t.after(() => rm(directory, {recursive: true, force: true}));
  return {store: new SqliteAuthorityStore(directory, "goal"), contender: new SqliteAuthorityStore(directory, "goal")};
}
registerAuthorityStoreConformance("SQLite", fixture);

for (const changedCursor of [1, 2]) {
  test(`SQLite validates historical receipt and scan lookahead at cursor ${changedCursor}`, async t => {
    const {store} = await fixture(t);
    let revision: string | null = null;
    for (let i = 1; i <= 3; i++) {
      const result = await store.commitAuthority(authorityStoreCommitFixture(revision, `op-${i}`, i, i));
      assert.equal(result.status, "applied"); if (result.status !== "applied") return;
      revision = result.provider_revision;
    }
    const {DatabaseSync} = createRequire(import.meta.url)("node:sqlite");
    const db = new DatabaseSync(store.path);
    db.prepare("UPDATE commits SET receipts=? WHERE cursor=?").run(JSON.stringify([{operation_id: "forged"}]), changedCursor);
    db.close();
    // The current row remains valid. Both returned historical rows and the
    // extra row used to decide has_more must independently verify their digest.
    for (const result of [await store.readReceipt(`op-${changedCursor}`), await store.scanCommitted(null, 1)]) {
      assert.equal(result.status, "failed");
      if (result.status === "failed") assert.equal(result.reason_code, "provider_protocol_violation");
    }
  });
}

for (const corruption of ["projection", "head_rollback", "gap", "receipt", "event", "missing_head", "invalid_json"] as const) {
  test(`SQLite rejects readable ${corruption} corruption without side effects`, async t => {
    const {store} = await fixture(t);
    let revision: string | null = null;
    for (let i = 1; i <= 3; i++) {
      const result = await store.commitAuthority(authorityStoreCommitFixture(revision, `op-${i}`, i, i));
      assert.equal(result.status, "applied"); if (result.status !== "applied") return;
      revision = result.provider_revision;
    }
    const {DatabaseSync} = createRequire(import.meta.url)("node:sqlite");
    const db = new DatabaseSync(store.path);
    if (corruption === "projection") db.prepare("UPDATE commits SET projection=? WHERE cursor=3").run(JSON.stringify({authority_revision: 999}));
    if (corruption === "receipt") db.exec("UPDATE commits SET receipts='[{\"operation_id\":\"forged\"}]' WHERE cursor=3");
    if (corruption === "event") db.exec("UPDATE commits SET events='[{\"type\":\"forged\"}]' WHERE cursor=3");
    if (corruption === "head_rollback") db.exec("UPDATE head SET cursor=1");
    if (corruption === "gap") db.exec("DELETE FROM commits WHERE cursor=2");
    if (corruption === "missing_head") db.exec("DELETE FROM head");
    if (corruption === "invalid_json") db.exec("UPDATE commits SET projection='{' WHERE cursor=3");
    db.close();
    const snapshot = () => {
      const reader = new DatabaseSync(store.path, {readOnly: true});
      try { return {head: reader.prepare("SELECT * FROM head").all(), commits: reader.prepare("SELECT * FROM commits ORDER BY cursor").all()}; }
      finally { reader.close(); }
    };
    const before = snapshot();
    for (const result of [await store.loadAuthority(), await store.readReceipt("op-1"),
      await store.scanCommitted(null, 1),
      await store.commitAuthority(authorityStoreCommitFixture(revision, "after-corruption", 4, 4))]) {
      assert.equal(result.status, "failed", JSON.stringify(result));
      if (result.status === "failed") assert.equal(result.reason_code, "provider_protocol_violation");
    }
    assert.deepEqual(snapshot(), before);
  });
}

test("SQLite reopens with stable identity and rejects unknown schema", async t => {
  const {store, contender} = await fixture(t);
  assert.deepEqual(await store.storeIdentity(), await contender.storeIdentity());
  const first = await store.commitAuthority(authorityStoreCommitFixture(null, "first", 1, 1));
  assert.equal(first.status, "applied");
  assert.deepEqual(await store.loadAuthority(), await contender.loadAuthority());
  const {DatabaseSync} = createRequire(import.meta.url)("node:sqlite");
  const db = new DatabaseSync(store.path);
  db.exec("PRAGMA user_version=99"); db.close();
  assert.equal((await contender.loadAuthority()).status, "failed");
  assert.equal((await contender.commitAuthority(authorityStoreCommitFixture(null, "bad", 2, 2))).status, "failed");
});

test("SQLite interrupted head publication rolls back receipt and outbox", async t => {
  const {store} = await fixture(t);
  const first = await store.commitAuthority(authorityStoreCommitFixture(null, "first", 1, 1));
  assert.equal(first.status, "applied"); if (first.status !== "applied") return;
  const before = await store.loadAuthority();
  const {DatabaseSync} = createRequire(import.meta.url)("node:sqlite");
  const db = new DatabaseSync(store.path);
  db.exec("CREATE TRIGGER interrupt_head BEFORE UPDATE ON head BEGIN SELECT RAISE(ABORT, 'interrupted'); END");
  db.close();
  assert.equal((await store.commitAuthority(authorityStoreCommitFixture(first.provider_revision, "second", 2, 2))).status, "failed");
  assert.deepEqual(await store.loadAuthority(), before);
  assert.deepEqual(await store.readReceipt("second"), {status: "missing"});
  const page = await store.scanCommitted(null, 10);
  assert.equal(page.status, "page");
  if (page.status === "page") assert.deepEqual(page.transactions.map(row => row.operation_id), ["first"]);
});

test("SQLite real processes serialize CAS and preserve a lost-response receipt", {timeout: 30000}, async t => {
  const {store} = await fixture(t);
  await store.storeIdentity();
  const directory = dirname(store.path);
  const start = (operation: string, revision = "null") => {
    const child = spawn(process.execPath, ["--no-warnings", "--experimental-sqlite", "--experimental-strip-types",
      fileURLToPath(new URL("./sqlite_authority_process.ts", import.meta.url)), directory, operation, revision],
    {stdio: ["pipe", "pipe", "pipe"]});
    let output = "", error = "";
    let ready: () => void = () => {};
    const readyPromise = new Promise<void>(resolve => {ready = resolve;});
    child.stdout.on("data", data => {output += String(data); if (output.includes("ready\n")) ready();});
    child.stderr.on("data", data => {error += String(data);});
    const done = new Promise<{code: number | null; output: string}>(resolve => child.on("close", code => {
      assert.equal(error, ""); resolve({code, output});
    }));
    t.after(() => child.kill());
    return {child, readyPromise, done};
  };
  const a = start("process-a"), b = start("process-b");
  await Promise.all([a.readyPromise, b.readyPromise]);
  a.child.stdin.end("go"); b.child.stdin.end("go");
  const outcomes = await Promise.all([a.done, b.done]);
  assert.deepEqual(outcomes.map(result => JSON.parse(result.output.split("\n")[1]!).status).sort(), ["applied", "conflict"]);
  const head = await store.loadAuthority(); assert.equal(head.status, "loaded");
  if (head.status !== "loaded") return;
  const lost = start("lost-response", head.provider_revision);
  await lost.readyPromise; lost.child.stdin.end("go");
  assert.equal((await lost.done).code, 23);
  assert.equal((await store.readReceipt("lost-response")).status, "found");
  const reopened = await store.loadAuthority();
  assert.equal(reopened.status, "loaded");
  if (reopened.status === "loaded") assert.equal(reopened.cursor, "2");
});
