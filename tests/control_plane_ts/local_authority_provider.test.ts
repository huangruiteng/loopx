import assert from "node:assert/strict";
import { mkdir, mkdtemp, readdir, readFile, rm, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import test from "node:test";
import { openLocalAuthorityStore, selectLocalSqliteAuthority } from "../../loopx/control_plane/coordination/local_authority_provider.ts";
import { SqliteAuthorityStore } from "../../loopx/control_plane/coordination/sqlite_authority_store.ts";
import { FileAuthorityStore } from "../../loopx/control_plane/coordination/file_authority_store.ts";
import { createRequire } from "node:module";
import { authorityStoreCommitFixture } from "./authority_store_conformance.ts";
import * as runtime from "../../loopx/control_plane/coordination/local_authority_runtime.ts";
import { qualifiedShadow, promotionRequest, engageFence } from "./local_promotion_fixture.ts";
import { loadLegacyCoordinationWriterFence, legacyCoordinationWriterFencePath } from "../../loopx/control_plane/coordination/legacy_writer_fence.ts";
import { acknowledgeLocalCoordinationTodoArchive, archiveLocalCoordinationTodos, listLocalCoordinationTodos, mutateLocalCoordinationAuthority } from "../../loopx/control_plane/coordination/local_authority_runtime.ts";

for (const [fault, source, reason] of [
  ["database_missing", "sqlite_v0", "local_authority_provider_missing"],
  ["database_corrupt", "sqlite_v0", "local_authority_provider_open_failed"],
  ["database_identity", "sqlite_v0", "local_authority_provider_identity_mismatch"],
  ["database_metadata", "sqlite_v0", "local_authority_provider_open_failed"],
  ["selector_unavailable", null, "local_authority_selector_unavailable"],
  ["selector_corrupt", null, "local_authority_selector_invalid"],
  ["selector_wrong_goal", null, "local_authority_selector_invalid"],
  ["selector_missing", null, "local_authority_selector_missing"],
] as const) {
  test(`selected provider ${fault} has accurate failure across runtime entrypoints and no fallback`, async t => {
    const directory = await root(t);
    await selectLocalSqliteAuthority(directory, "goal-a", true);
    const store = await openLocalAuthorityStore(directory, "goal-a");
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
    if (fault === "selector_unavailable") { await rm(marker); await mkdir(marker); }
    if (fault === "selector_corrupt") await writeFile(marker, "{");
    if (fault === "selector_wrong_goal") {
      const config = JSON.parse(await readFile(marker, "utf8"));
      await writeFile(marker, JSON.stringify({...config, goal_id: "another-goal"}));
    }
    if (fault === "selector_missing") await rm(marker);
    const bytes = async (path: string) => readFile(path).catch(error => {
      if (error.code === "ENOENT") return null;
      if (error.code === "EISDIR" || error.code === "EPERM") return "unreadable";
      throw error;
    });
    const before = await Promise.all([bytes(store.path), bytes(marker)]);
    await assert.rejects(openLocalAuthorityStore(directory, "goal-a"), {reasonCode: reason, sourceAuthority: source});
    for (const dryRun of [false, true]) {
      for (const [name, invoke] of providerCalls(directory, `${identity.store_identity}:1`, dryRun)) {
        const result: Record<string, unknown> = await invoke();
        assert.equal(result.status, "failed", name);
        assert.equal(result.source_authority, source, name);
        assert.equal(result.reason_code, reason, name);
        assert.equal(result.legacy_fallback_used, false, name);
        assert.equal(result.decision_read_from_provider, false, name);
        if (name === "promoteLocalCoordinationAuthority") assert.equal(result.legacy_writer_fenced, false);
        if (fault === "database_metadata") assert.equal(result.provider_reason_code, "provider_protocol_violation");
        if (fault === "database_identity") assert.equal(result.provider_reason_code, undefined);
        assert.deepEqual(await Promise.all([bytes(store.path), bytes(marker)]), before, name);
      }
    }
    assert.equal((await loadLegacyCoordinationWriterFence(directory, "goal-a")).status, "missing");
    // Even an existing fence cannot be claimed as verified if opening fails
    // first. Its independent existence does not replace this call's readback.
    const promotion = promotionRequest(directory, {}, "file:synthetic:1");
    await writeFile(join(directory, "ACTIVE_GOAL_STATE.md"), "# Synthetic source\n");
    await engageFence(promotion);
    const fenced = await loadLegacyCoordinationWriterFence(directory, "goal-a");
    assert.equal(fenced.status, "loaded");
    const failedPromotion = await runtime.promoteLocalCoordinationAuthority(promotion);
    assert.equal(failedPromotion.reason_code, reason);
    assert.equal(failedPromotion.legacy_writer_fenced, false);
    assert.deepEqual(await loadLegacyCoordinationWriterFence(directory, "goal-a"), fenced);

    assert.deepEqual(await Promise.all([bytes(store.path), bytes(marker)]), before);
    assert.equal((await readdir(join(directory, "authority"))).includes("file-v0"), false);
  });
}

// Valid transport to each owning runtime entrypoint; failed opening must be
// independent of dry-run, command family, and the caller's requested mutation.
function providerCalls(directory: string, revision: string, dryRun: boolean) {
  const input = {runtime_root: directory, goal_id: "goal-a", todo_id: "todo-a", role: "agent",
    operation_id: "open-failure", expected_provider_revision: revision, dry_run: dryRun,
    registered_agents: ["agent-a"], actor_agent_id: "agent-a", claimed_by: "agent-a",
    observed_at: "2026-09-08T01:00:00Z", clear_fields: [], patch: {text: "Correction"},
    lifecycle_grants: [], successor_intents: [], linked_successor_todo_ids: []};
  type Entrypoint = {[K in keyof typeof runtime]: typeof runtime[K] extends
    (value: unknown) => Promise<unknown> ? K : never}[keyof typeof runtime];
  // A new exported runtime action must deliberately enter this failure matrix.
  const requests = {
    listLocalCoordinationTodos: [{...input, schema_version: runtime.LOCAL_COORDINATION_TODO_LIST_REQUEST_SCHEMA}],
    readLocalCoordinationTodo: [{...input, schema_version: runtime.LOCAL_COORDINATION_TODO_READ_REQUEST_SCHEMA}],
    mutateLocalCoordinationAuthority: [{...input, schema_version: runtime.LOCAL_COORDINATION_MUTATION_REQUEST_SCHEMA,
      mutations: [{kind: "todo_remove", todo_id: "todo-a"}]}],
    createLocalCoordinationTodo: [{...input, schema_version: "loopx_local_coordination_todo_create_request_v0", todo: {}}],
    claimLocalCoordinationTodo: [{...input, schema_version: runtime.LOCAL_COORDINATION_TODO_CLAIM_REQUEST_SCHEMA}],
    updateLocalCoordinationTodo: [
      {...input, schema_version: "loopx_local_coordination_todo_update_request_v0"},
      {...input, schema_version: "loopx_local_coordination_todo_update_request_v1", planning_intent: {status: "blocked"}}],
    editLocalCoordinationTodo: [input],
    terminalLifecycleLocalCoordinationTodo: [{...input, schema_version: runtime.LOCAL_COORDINATION_TODO_TERMINAL_LIFECYCLE_REQUEST_SCHEMA}],
    archiveLocalCoordinationTodos: [{...input, schema_version: runtime.LOCAL_COORDINATION_TODO_ARCHIVE_REQUEST_SCHEMA, max_active_done: 0}],
    acknowledgeLocalCoordinationTodoArchive: [{...input, schema_version: runtime.LOCAL_COORDINATION_TODO_ARCHIVE_ACK_REQUEST_SCHEMA}],
    promoteLocalCoordinationAuthority: [promotionRequest(directory, {}, "file:synthetic:1")],
    pollLocalCoordinationMonitor: [{...input, schema_version: "loopx_coordination_monitor_poll_request_v0", observation: {}, intent: {}}],
    continueLocalTodo: [{...input, schema_version: "loopx_local_coordination_todo_continuation_request_v0",
      todo_id: "todo-a", agent_id: "agent-a", session_id: "session-1", action: "inspect",
      registered_agents: ["agent-a", "agent-b"]}],
  } satisfies Record<Entrypoint, unknown[]>;
  return Object.entries(requests).flatMap(([name, values]) => values.map(value =>
    [name, () => runtime[name as Entrypoint](value)] as const));
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


for (const provider of ["file", "sqlite"] as const) {
  for (const phase of ["fence_missing", "fence_corrupt", "fence_mismatch", "shadow_missing",
    "shadow_invalid", "qualification", "replay", "receipt_missing", "lineage_mismatch"] as const) {
    test(`${provider} promotion evidence follows verified state at ${phase}`, async t => {
      const directory = await root(t);
      if (provider === "sqlite") await selectLocalSqliteAuthority(directory, "goal-a", true);
      const canonical = await openLocalAuthorityStore(directory, "goal-a");
      const shadow = await qualifiedShadow(directory);
      const shadowStore = new FileAuthorityStore(join(directory, "authority-shadow", "file-v0"), "goal-a");
      const request = promotionRequest(directory, shadow.projection, shadow.providerRevision);
      if (phase === "shadow_invalid") {
        // A valid store row can still contain an invalid domain projection.
        const projection = {...shadow.projection, goal_id: "different-goal"};
        const committed = await shadowStore.commitAuthority({operation_id: "invalid-domain",
          expected_provider_revision: shadow.providerRevision, next_projection: projection, receipts: [], events: []});
        assert.equal(committed.status, "applied"); if (committed.status !== "applied") return;
        Object.assign(request, promotionRequest(directory, projection, committed.provider_revision));
      }
      if (phase !== "fence_missing") await engageFence(request);
      const fencePath = legacyCoordinationWriterFencePath(directory, "goal-a");
      if (phase === "fence_corrupt") await writeFile(fencePath, "{");
      if (phase === "fence_mismatch") {
        await writeFile(fencePath, JSON.stringify({...request.writer_fence, fence_id: "different-fence"}));
      }
      if (phase === "shadow_missing") await rm(join(directory, "authority-shadow", "file-v0"), {recursive: true});
      if (["replay", "receipt_missing", "lineage_mismatch"].includes(phase)) {
        // Seed an already-committed qualification fixture; this does not grant
        // permission for a new cutover through the current qualification gate.
        const receipt = {schema_version: runtime.LOCAL_COORDINATION_PROMOTION_RECEIPT_SCHEMA,
          operation_id: request.operation_id, goal_id: request.goal_id,
          source_shadow_provider_revision: request.expected_shadow_provider_revision,
          source_projection_sha256: request.expected_shadow_projection_sha256,
          writer_fence_id: request.writer_fence.fence_id, source_version: request.writer_fence.source_version};
        const seeded = await canonical.commitAuthority({operation_id: phase === "receipt_missing" ? "other-operation" : request.operation_id,
          expected_provider_revision: null, next_projection: phase === "lineage_mismatch" ?
            {...shadow.projection, extra: "different snapshot"} : shadow.projection,
          receipts: phase === "receipt_missing" ? [] : [receipt], events: []});
        assert.equal(seeded.status, "applied");
      }
      const before = await canonical.loadAuthority();
      const fenceBefore = await loadLegacyCoordinationWriterFence(directory, "goal-a");
      const result = await runtime.promoteLocalCoordinationAuthority(request);
      const verified = !["fence_missing", "fence_corrupt", "fence_mismatch"].includes(phase);
      assert.equal(result.legacy_writer_fenced, verified, JSON.stringify(result));
      assert.equal(result.legacy_fallback_used, false);
      assert.equal(result.status, phase === "replay" ? "replayed" : "failed", JSON.stringify(result));
      const reasons = {fence_missing: "local_authority_writer_fence_not_verified",
        fence_corrupt: "legacy_writer_fence_read_failed", fence_mismatch: "local_authority_writer_fence_not_verified",
        shadow_missing: "local_authority_shadow_missing", shadow_invalid: "local_authority_promotion_unavailable",
        qualification: "local_authority_shadow_not_qualified", receipt_missing: "local_authority_promotion_receipt_missing",
        lineage_mismatch: "local_authority_promotion_lineage_mismatch"};
      if (phase !== "replay") assert.equal(result.reason_code, reasons[phase]);
      else assert.equal(result.canonical_authority, provider === "sqlite" ? "sqlite_v0" : "file_v0");
      assert.deepEqual(await canonical.loadAuthority(), before);
      assert.deepEqual(await loadLegacyCoordinationWriterFence(directory, "goal-a"), fenceBefore);
      if (provider === "sqlite") assert.equal((await readdir(join(directory, "authority"))).includes("file-v0"), false);
    });
  }
}
