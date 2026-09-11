import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, rm, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import test from "node:test";
import { openLocalAuthorityStore, selectLocalSqliteAuthority } from "../../loopx/control_plane/coordination/local_authority_provider.ts";
import { SqliteAuthorityStore } from "../../loopx/control_plane/coordination/sqlite_authority_store.ts";
import { FileAuthorityStore } from "../../loopx/control_plane/coordination/file_authority_store.ts";
import { createRequire } from "node:module";
import { authorityStoreCommitFixture } from "./authority_store_conformance.ts";
import { acknowledgeLocalCoordinationTodoArchive, archiveLocalCoordinationTodos, listLocalCoordinationTodos, mutateLocalCoordinationAuthority } from "../../loopx/control_plane/coordination/local_authority_runtime.ts";

for (const [fault, source, reason] of [
  ["database_missing", "sqlite_v0", "local_authority_provider_missing"],
  ["database_corrupt", "sqlite_v0", "local_authority_provider_open_failed"],
  ["database_identity", "sqlite_v0", "local_authority_provider_identity_mismatch"],
  ["database_metadata", "sqlite_v0", "local_authority_provider_open_failed"],
  ["selector_corrupt", null, "local_authority_selector_invalid"],
  ["selector_wrong_goal", null, "local_authority_selector_invalid"],
  ["selector_missing", null, "local_authority_selector_missing"],
] as const) {
  test(`selected provider ${fault} has accurate read/write failure and no fallback`, async t => {
    const directory = await root(t);
    await selectLocalSqliteAuthority(directory, "goal", true);
    const store = await openLocalAuthorityStore(directory, "goal");
    assert.ok(store instanceof SqliteAuthorityStore);
    const identity = await store.storeIdentity();
    assert.equal(identity.status, "available"); if (identity.status !== "available") return;
    const markerName = (await readdir(join(directory, "authority"))).find(name => name.startsWith("provider-"))!;
    const marker = join(directory, "authority", markerName);
    if (fault === "database_missing") await rename(store.path, store.path + ".saved");
    if (fault === "database_corrupt") await writeFile(store.path, "not a SQLite database");
    if (fault === "database_identity" || fault === "database_metadata") {
      const {DatabaseSync} = createRequire(import.meta.url)("node:sqlite");
      const db = new DatabaseSync(store.path);
      db.prepare("UPDATE metadata SET store_identity=?").run(fault === "database_identity" ? "sqlite:" + "0".repeat(32) : "invalid-identity");
      db.close();
    }
    if (fault === "selector_corrupt") await writeFile(marker, "{");
    if (fault === "selector_wrong_goal") {
      const config = JSON.parse(await readFile(marker, "utf8"));
      await writeFile(marker, JSON.stringify({...config, goal_id: "another-goal"}));
    }
    if (fault === "selector_missing") await rm(marker);
    const bytes = async (path: string) => readFile(path).catch(error => {
      if (error.code === "ENOENT") return null;
      throw error;
    });
    const before = await Promise.all([bytes(store.path), bytes(marker)]);
    await assert.rejects(openLocalAuthorityStore(directory, "goal"), {reasonCode: reason, sourceAuthority: source});
    const input = {runtime_root: directory, goal_id: "goal"};
    const read = await listLocalCoordinationTodos({...input, schema_version: "loopx_local_coordination_todo_list_request_v0"});
    const write = await mutateLocalCoordinationAuthority({...input, schema_version: "loopx_local_coordination_mutation_request_v0",
      operation_id: "open-failure", expected_provider_revision: `${identity.store_identity}:1`, mutations: [{kind: "todo_remove", todo_id: "todo-a"}]});
    const ack = await acknowledgeLocalCoordinationTodoArchive({...input,
      schema_version: "loopx_local_coordination_todo_archive_ack_request_v0",
      role: "agent", operation_id: "archive-a"});
    for (const result of [read, write, ack]) {
      assert.equal(result.status, "failed");
      assert.equal(result.source_authority, source);
      assert.equal(result.reason_code, reason);
      assert.equal(result.legacy_fallback_used, false);
      assert.equal(result.decision_read_from_provider, false);
      if (fault === "database_metadata") assert.equal(result.provider_reason_code, "provider_protocol_violation");
      if (fault === "database_identity") assert.equal(result.provider_reason_code, undefined);
    }
    assert.deepEqual(await Promise.all([bytes(store.path), bytes(marker)]), before);
    assert.equal((await readdir(join(directory, "authority"))).includes("file-v0"), false);
  });
}

async function root(t: test.TestContext) {
  const path = await mkdtemp(join(tmpdir(), "provider-selection-"));
  t.after(() => rm(path, {recursive: true, force: true}));
  return path;
}

test("SQLite opt-in is persistent and default-off with a read-only preview", async t => {
  const directory = await root(t);
  assert.ok(await openLocalAuthorityStore(directory, "goal") instanceof FileAuthorityStore);
  assert.deepEqual(await selectLocalSqliteAuthority(directory, "goal", false),
    {ok: true, provider: "sqlite", executed: false, changed: false});
  assert.equal((await readdir(directory, {recursive: true})).some(path => path.endsWith(".sqlite")), false);
  assert.equal((await selectLocalSqliteAuthority(directory, "goal", true)).changed, true);
  const store = await openLocalAuthorityStore(directory, "goal");
  assert.ok(store instanceof SqliteAuthorityStore);
  const bytes = await readFile(store.path);
  await store.storeIdentity(); await store.loadAuthority();
  assert.deepEqual(await readFile(store.path), bytes);
  assert.equal((await selectLocalSqliteAuthority(directory, "goal", true)).changed, false);
  assert.ok(await openLocalAuthorityStore(directory, "another-goal") instanceof FileAuthorityStore);
});

test("SQLite selection cannot replace existing canonical authority", async t => {
  const directory = await root(t);
  const store = await openLocalAuthorityStore(directory, "goal");
  assert.equal((await store.commitAuthority(authorityStoreCommitFixture(null, "first", 1, 1))).status, "applied");
  await assert.rejects(selectLocalSqliteAuthority(directory, "goal", true), /cannot replace/);
  assert.ok(await openLocalAuthorityStore(directory, "goal") instanceof FileAuthorityStore);
});

test("Lost database or selector never causes fallback or lineage recreation", async t => {
  const directory = await root(t);
  await selectLocalSqliteAuthority(directory, "goal", true);
  const store = await openLocalAuthorityStore(directory, "goal");
  assert.ok(store instanceof SqliteAuthorityStore);
  await rename(store.path, store.path + ".saved");
  await assert.rejects(openLocalAuthorityStore(directory, "goal"), /database is missing/);
  assert.equal((await store.commitAuthority(authorityStoreCommitFixture(null, "bad", 1, 1))).status, "failed");
  await rename(store.path + ".saved", store.path);
  const marker = (await readdir(join(directory, "authority"))).find(name => name.startsWith("provider-"))!;
  await rm(join(directory, "authority", marker));
  await assert.rejects(openLocalAuthorityStore(directory, "goal"), /selector is missing/);
});

// Opening must not remove the per-operation lineage fence.
test("opened SQLite store rejects lineage replacement before its next operation", async t => {
  const directory = await root(t);
  await selectLocalSqliteAuthority(directory, "goal", true);
  const store = await openLocalAuthorityStore(directory, "goal");
  assert.ok(store instanceof SqliteAuthorityStore);
  const {DatabaseSync} = createRequire(import.meta.url)("node:sqlite");
  const db = new DatabaseSync(store.path);
  db.prepare("UPDATE metadata SET store_identity=?").run("sqlite:" + "0".repeat(32));
  db.close();
  const before = await readFile(store.path);
  assert.equal((await store.loadAuthority()).status, "failed");
  assert.equal((await store.commitAuthority(authorityStoreCommitFixture(null, "replacement", 1, 1))).status, "failed");
  assert.deepEqual(await readFile(store.path), before);
});


test("SQLite archive acknowledgement retires the accepted attempt without changing authority", async t => {
  const directory = await root(t);
  await selectLocalSqliteAuthority(directory, "goal", true);
  const store = await openLocalAuthorityStore(directory, "goal");
  const {canonicalAuthoritySha256} = await import("../../loopx/control_plane/coordination/authority_store_codec.ts");
  const {TODO_CANONICAL_READ_RECORD_FIELDS, TODO_CANONICAL_READ_RECORD_SCHEMA} =
    await import("../../loopx/control_plane/coordination/coordination_projection.ts");
  const todos = [{schema_version: "todo_item_v0", todo_id: "done-a", role: "agent",
    status: "done", done: true, text: "Completed task", archive_state: "active", source_section: "Agent Todo"}];
  const seed = await store.commitAuthority({operation_id: "seed", expected_provider_revision: null,
    events: [], receipts: [], next_projection: {goal_id: "goal", handoff_mode: "soft_claim", todos, leases: [],
      todo_read_model: {schema_version: TODO_CANONICAL_READ_RECORD_SCHEMA, todo_count: 1,
        records_sha256: canonicalAuthoritySha256(todos), contract_fields: [...TODO_CANONICAL_READ_RECORD_FIELDS]}}});
  assert.equal(seed.status, "applied"); if (seed.status !== "applied") return;
  const archived = await archiveLocalCoordinationTodos({
    schema_version: "loopx_local_coordination_todo_archive_request_v0", runtime_root: directory,
    goal_id: "goal", role: "agent", max_active_done: 0, operation_id: "archive-a",
    expected_provider_revision: seed.provider_revision, dry_run: false, observed_at: "2026-09-08T01:00:00Z"});
  assert.equal(archived.status, "applied", JSON.stringify(archived));
  assert.deepEqual(archived.moved_todo_ids, ["done-a"]);
  const before = await store.loadAuthority();
  const request = {schema_version: "loopx_local_coordination_todo_archive_ack_request_v0",
    runtime_root: directory, goal_id: "goal", role: "agent", operation_id: "archive-a"};
  assert.equal((await acknowledgeLocalCoordinationTodoArchive(request)).status, "acknowledged");
  assert.equal((await acknowledgeLocalCoordinationTodoArchive(request)).status, "no_change");
  assert.deepEqual(await store.loadAuthority(), before);
  assert.equal((await readdir(join(directory, "authority"))).includes("file-v0"), false);
});
