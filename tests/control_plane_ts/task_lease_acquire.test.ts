import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { type TestContext } from "node:test";

import {
  executeTaskLeaseAcquire,
  leaseInteger,
  TaskLeaseAcquireError,
  TASK_LEASE_ACQUIRE_REQUEST_SCHEMA_VERSION,
} from "../../loopx/control_plane/work_items/task_lease_acquire.ts";
import {
  LEGACY_COORDINATION_WRITER_FENCE_ENGAGE_REQUEST_SCHEMA,
  LEGACY_COORDINATION_WRITER_FENCE_SCHEMA,
  LEGACY_COORDINATION_WRITE_CHECK_RESULT_SCHEMA,
} from "../../loopx/control_plane/coordination/coordination_state_contract.generated.ts";
import { engageLegacyCoordinationWriterFence } from "../../loopx/control_plane/coordination/legacy_writer_fence.ts";

const FIXED_NOW = new Date("2026-08-27T03:00:00.000Z");

async function workspace(t: TestContext): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "loopx-task-lease-native-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  return root;
}

async function sourceReceipt(
  root: string,
  content = "authority-v1",
): Promise<Record<string, unknown>> {
  const path = join(root, "authority-source.json");
  await writeFile(path, content, "utf8");
  return {
    source_id: "authority",
    path,
    state: "file",
    sha256: createHash("sha256").update(content).digest("hex"),
  };
}

async function request(
  root: string,
  overrides: Record<string, unknown> = {},
): Promise<Record<string, unknown>> {
  const authority = {
    handoff_mode: "legacy",
    registered_agent_candidates: [["agent-a", "agent-b"]],
    todos: [
      {
        todo_id: "todo_target",
        status: "open",
        claimed_by: null,
        excluded_agents: [],
      },
      {
        todo_id: "todo_other",
        status: "open",
        claimed_by: null,
        excluded_agents: [],
      },
    ],
    todo_projection_error: null,
    source_receipts: [await sourceReceipt(root)],
    ...((overrides.authority as Record<string, unknown> | undefined) ?? {}),
  };
  return {
    schema_version: TASK_LEASE_ACQUIRE_REQUEST_SCHEMA_VERSION,
    runtime_root: join(root, "runtime"),
    goal_id: "goal-a",
    todo_id: "todo_target",
    owner: "agent-a",
    idempotency_key: "turn-1",
    ttl_seconds: 120,
    write_scopes: ["loopx/**"],
    expected_version: null,
    ...overrides,
    authority,
  };
}

function leasePath(root: string, todoId = "todo_target"): string {
  return join(root, "runtime", "goals", "goal-a", "task-leases", `${todoId}.json`);
}

async function persistedLease(
  root: string,
  todoId = "todo_target",
): Promise<Record<string, unknown>> {
  return JSON.parse(await readFile(leasePath(root, todoId), "utf8"));
}

test("native acquire owns validation, generation, persistence, and canonical receipts", async (t) => {
  const root = await workspace(t);
  const result = await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });

  assert.equal(result.ok, true);
  assert.equal(result.acquired, true);
  assert.equal(result.idempotent, false);
  assert.equal("handoff_mode" in result, false);
  assert.deepEqual(result.settlement, {
    effect_id: "goal-a:agent-a:todo_target:turn-1",
    receipts: [
      { step: "validation", status: "committed", effect_id: "goal-a:agent-a:todo_target:turn-1" },
      {
        step: "durable_writeback",
        status: "committed",
        effect_id: "goal-a:agent-a:todo_target:turn-1",
      },
    ],
  });
  assert.deepEqual(await persistedLease(root), {
    schema_version: "task_lease_v0",
    goal_id: "goal-a",
    todo_id: "todo_target",
    owner: "agent-a",
    idempotency_key: "turn-1",
    write_scopes: ["loopx/**"],
    acquire_ttl_seconds: 120,
    version: 1,
    lease_epoch: 1,
    acquired_at: "2026-08-27T03:00:00Z",
    updated_at: "2026-08-27T03:00:00Z",
    expires_at: "2026-08-27T03:02:00Z",
    status: "active",
  });
});

test("exact replay is idempotent and does not rewrite the lease", async (t) => {
  const root = await workspace(t);
  let writes = 0;
  const first = await executeTaskLeaseAcquire(await request(root), {
    now: () => FIXED_NOW,
    beforeWrite: () => {
      writes += 1;
    },
  });
  const second = await executeTaskLeaseAcquire(await request(root), {
    now: () => new Date("2026-08-27T03:00:30.000Z"),
    beforeWrite: () => {
      writes += 1;
    },
  });

  assert.equal(first.acquired, true);
  assert.equal(second.acquired, false);
  assert.equal(second.idempotent, true);
  assert.equal(writes, 1);
  assert.equal(
    (second.settlement as Record<string, unknown>).effect_id,
    "goal-a:agent-a:todo_target:turn-1",
  );
  assert.equal((await persistedLease(root)).version, 1);
});

test("replay key reuse, CAS mismatch, and active same-todo contention stay typed", async (t) => {
  const root = await workspace(t);
  await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });

  const reuse = await executeTaskLeaseAcquire(
    await request(root, { ttl_seconds: 300 }),
    { now: () => FIXED_NOW },
  );
  assert.equal(reuse.ok, false);
  assert.equal(reuse.error_code, "idempotency_key_reuse");
  assert.equal(
    (reuse.settlement as Record<string, unknown>).effect_id,
    "goal-a:agent-a:todo_target:turn-1",
  );

  const mismatch = await executeTaskLeaseAcquire(
    await request(root, { idempotency_key: "turn-2", expected_version: 0 }),
    { now: () => FIXED_NOW },
  );
  assert.equal(mismatch.error_code, "version_mismatch");
  assert.equal(mismatch.actual_version, 1);

  const contention = await executeTaskLeaseAcquire(
    await request(root, { owner: "agent-b", idempotency_key: "turn-b" }),
    { now: () => FIXED_NOW },
  );
  assert.equal(contention.error_code, "todo_lease_conflict");
});

test("retired generations reject key reuse and mint monotonic version and epoch", async (t) => {
  const root = await workspace(t);
  await mkdir(join(root, "runtime", "goals", "goal-a", "task-leases"), { recursive: true });
  await writeFile(
    leasePath(root),
    `${JSON.stringify({
      schema_version: "task_lease_v0",
      goal_id: "goal-a",
      todo_id: "todo_target",
      owner: "agent-a",
      idempotency_key: "retired-key",
      write_scopes: ["loopx/**"],
      acquire_ttl_seconds: 120,
      version: 7,
      status: "released",
      expires_at: "2026-08-27T02:00:00.000Z",
    }, null, 2)}\n`,
    "utf8",
  );

  const reuse = await executeTaskLeaseAcquire(
    await request(root, { idempotency_key: "retired-key" }),
    { now: () => FIXED_NOW },
  );
  assert.equal(reuse.error_code, "idempotency_key_reuse");
  assert.match(String(reuse.error), /expired or released/u);

  const acquired = await executeTaskLeaseAcquire(
    await request(root, { idempotency_key: "new-key", expected_version: 7 }),
    { now: () => FIXED_NOW },
  );
  assert.equal(acquired.ok, true);
  assert.equal((await persistedLease(root)).version, 8);
  assert.equal((await persistedLease(root)).lease_epoch, 2);
});

test("timezone-less legacy expiration remains UTC", async (t) => {
  const root = await workspace(t);
  await mkdir(join(root, "runtime", "goals", "goal-a", "task-leases"), { recursive: true });
  await writeFile(
    leasePath(root),
    JSON.stringify({
      schema_version: "task_lease_v0",
      todo_id: "todo_target",
      owner: "agent-b",
      idempotency_key: "legacy-owner",
      write_scopes: [],
      version: 1,
      lease_epoch: 1,
      status: "active",
      expires_at: "2026-08-27T04:00:00",
    }),
    "utf8",
  );

  const result = await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });

  assert.equal(result.error_code, "todo_lease_conflict");
});

test("effective overlapping leases conflict while ineligible leases self-disarm", async (t) => {
  const root = await workspace(t);
  await mkdir(join(root, "runtime", "goals", "goal-a", "task-leases"), { recursive: true });
  await writeFile(
    leasePath(root, "todo_other"),
    `${JSON.stringify({
      schema_version: "task_lease_v0",
      goal_id: "goal-a",
      todo_id: "todo_other",
      owner: "agent-b",
      idempotency_key: "other-key",
      write_scopes: ["loopx/control_plane/**"],
      acquire_ttl_seconds: 120,
      version: 4,
      lease_epoch: 3,
      status: "active",
      expires_at: "2026-08-27T04:00:00.000Z",
    }, null, 2)}\n`,
    "utf8",
  );

  const conflict = await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });
  assert.equal(conflict.error_code, "write_scope_conflict");
  assert.equal((conflict.conflicts as unknown[]).length, 1);

  const authority = {
    registered_agent_candidates: [["agent-a", "agent-b"]],
    todos: [
      { todo_id: "todo_target", status: "open", claimed_by: null, excluded_agents: [] },
      { todo_id: "todo_other", status: "done", claimed_by: null, excluded_agents: [] },
    ],
  };
  const acquired = await executeTaskLeaseAcquire(
    await request(root, { authority }),
    { now: () => FIXED_NOW },
  );
  assert.equal(acquired.ok, true);
});

test("legacy scope strings retain Python splitting and fnmatch behavior", async (t) => {
  const root = await workspace(t);
  await mkdir(join(root, "runtime", "goals", "goal-a", "task-leases"), { recursive: true });
  await writeFile(
    leasePath(root, "todo_other"),
    `${JSON.stringify({
      schema_version: "task_lease_v0",
      todo_id: "todo_other",
      owner: "agent-b",
      idempotency_key: "other-key",
      write_scopes: "docs/[!a]*;src/**",
      version: 1,
      lease_epoch: 1,
      status: "active",
      expires_at: "2026-08-27T04:00:00Z",
    }, null, 2)}\n`,
    "utf8",
  );

  const result = await executeTaskLeaseAcquire(
    await request(root, { write_scopes: ["docs/beta"] }),
    { now: () => FIXED_NOW },
  );

  assert.equal(result.error_code, "write_scope_conflict");
  assert.equal(
    ((result.conflicts as Record<string, unknown>[])[0]).write_scopes,
    "docs/[!a]*;src/**",
  );
});

test("handoff and owner eligibility failures happen before persistence", async (t) => {
  const root = await workspace(t);
  const soft = await executeTaskLeaseAcquire(
    await request(root, { authority: { handoff_mode: "soft_claim" } }),
    { now: () => FIXED_NOW },
  );
  assert.equal(soft.error_code, "handoff_mode_forbids_lease");

  const unregistered = await executeTaskLeaseAcquire(
    await request(root, { owner: "agent-c" }),
    { now: () => FIXED_NOW },
  );
  assert.equal(unregistered.error_code, "owner_not_registered");
  assert.equal(
    (unregistered.settlement as Record<string, unknown>).effect_id,
    null,
  );

  const recursivelyNested = await executeTaskLeaseAcquire(
    await request(root, {
      authority: { registered_agent_candidates: [["agent-b", ["agent-a"]]] },
    }),
    { now: () => FIXED_NOW },
  );
  assert.equal(recursivelyNested.error_code, "owner_not_registered");

  const claimed = await executeTaskLeaseAcquire(
    await request(root, {
      authority: {
        todos: [{
          todo_id: "todo_target",
          status: "open",
          claimed_by: "agent-b",
          excluded_agents: [],
        }],
      },
    }),
    { now: () => FIXED_NOW },
  );
  assert.equal(claimed.error_code, "owner_conflicts_with_claim");
  await assert.rejects(() => readFile(leasePath(root), "utf8"), { code: "ENOENT" });
});

test("post-identity failures preserve the legacy validation receipt prefix", async (t) => {
  const root = await workspace(t);
  const invalidTtl = await executeTaskLeaseAcquire(
    await request(root, { ttl_seconds: 0 }),
    { now: () => FIXED_NOW },
  );

  assert.equal(invalidTtl.error_code, "invalid_ttl");
  assert.deepEqual(invalidTtl.settlement, {
    effect_id: "goal-a:agent-a:todo_target:turn-1",
    receipts: [{
      step: "validation",
      status: "committed",
      effect_id: "goal-a:agent-a:todo_target:turn-1",
    }],
    failure: {
      step: "durable_writeback",
      kind: "invalid_identity",
      code: "invalid_ttl",
    },
  });
});

test("an engaged legacy writer fence rejects acquire before validation without receipts", async (t) => {
  // Baseline reported a committed validation receipt and a durable_writeback
  // failure for this rejection although no writeback was attempted; the
  // fence is a terminal permission decision taken by the promoted authority
  // before the first side effect (RFC section 5 `rejected`, section 5.6,
  // Appendix C), so it is typed like every other validation-stage denial and
  // like its renew/transfer/release siblings.
  const root = await workspace(t);
  await mkdir(join(root, "runtime"), { recursive: true });
  await writeFile(join(root, "ACTIVE_GOAL_STATE.md"), "---\ngoal_id: goal-a\n---\n\n## Agent Todo\n\n", "utf8");
  const engaged = await engageLegacyCoordinationWriterFence({
    schema_version: LEGACY_COORDINATION_WRITER_FENCE_ENGAGE_REQUEST_SCHEMA,
    runtime_root: join(root, "runtime"),
    goal_id: "goal-a",
    state_path: join(root, "ACTIVE_GOAL_STATE.md"),
    fence: {
      schema_version: LEGACY_COORDINATION_WRITER_FENCE_SCHEMA,
      state: "engaged",
      goal_id: "goal-a",
      fence_id: "legacy-writer-fence:goal-a:state-1",
      source_version: "state:1",
      source_projection_sha256: "a".repeat(64),
      expected_shadow_provider_revision: "file:1:aaaaaaaaaaaaaaaaaaaaaaaa",
    },
  });
  assert.equal(engaged.status, "applied");

  const fenced = await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });

  assert.equal(fenced.ok, false);
  assert.equal(fenced.schema_version, "task_lease_v0");
  assert.equal(fenced.error_code, "legacy_coordination_writer_fenced");
  assert.equal(
    fenced.error,
    "legacy coordination writer is fenced; use the promoted canonical authority (file_v0) for goal goal-a; fence legacy-writer-fence:goal-a:state-1; the primary record was not changed",
  );
  assert.deepEqual(fenced.write_check, {
    schema_version: LEGACY_COORDINATION_WRITE_CHECK_RESULT_SCHEMA,
    status: "blocked",
    reason_code: "legacy_coordination_writer_fenced",
    authority_mode: "file_v0",
    fence_id: "legacy-writer-fence:goal-a:state-1",
  });
  assert.deepEqual(fenced.settlement, {
    effect_id: null,
    receipts: [],
    failure: {
      step: "validation",
      kind: "permission_denied",
      code: "legacy_coordination_writer_fenced",
    },
  });
  await assert.rejects(() => readFile(leasePath(root), "utf8"), { code: "ENOENT" });
});

test("invalid settlement identities fail validation without receipts", async (t) => {
  const root = await workspace(t);
  const invalidOwner = await executeTaskLeaseAcquire(
    await request(root, { owner: "bad owner!" }),
    { now: () => FIXED_NOW },
  );

  assert.equal(invalidOwner.error_code, "invalid_owner");
  assert.deepEqual(invalidOwner.settlement, {
    effect_id: null,
    receipts: [],
    failure: {
      step: "validation",
      kind: "invalid_identity",
      code: "invalid_owner",
    },
  });
});

test("source CAS rejects stale authority facts before lease read or write", async (t) => {
  const root = await workspace(t);
  const input = await request(root);
  await writeFile(join(root, "authority-source.json"), "authority-v2", "utf8");

  const result = await executeTaskLeaseAcquire(input, { now: () => FIXED_NOW });

  assert.equal(result.error_code, "authority_source_changed");
  assert.deepEqual(result.changed_sources, ["authority"]);
  await assert.rejects(() => readFile(leasePath(root), "utf8"), { code: "ENOENT" });
});

test("source CAS is rechecked after the decision and immediately before write", async (t) => {
  const root = await workspace(t);
  const input = await request(root);

  const result = await executeTaskLeaseAcquire(input, {
    now: () => FIXED_NOW,
    beforeWrite: () => writeFile(
      join(root, "authority-source.json"),
      "authority-changed-after-decision",
      "utf8",
    ),
  });

  assert.equal(result.error_code, "authority_source_changed");
  await assert.rejects(() => readFile(leasePath(root), "utf8"), { code: "ENOENT" });
});

test("failed pre-write attempt leaves no partial lease and a retry succeeds", async (t) => {
  const root = await workspace(t);
  const input = await request(root);
  await assert.rejects(
    () => executeTaskLeaseAcquire(input, {
      now: () => FIXED_NOW,
      beforeWrite: () => {
        throw new Error("simulated crash");
      },
    }),
    /simulated crash/u,
  );
  await assert.rejects(() => readFile(leasePath(root), "utf8"), { code: "ENOENT" });

  const retry = await executeTaskLeaseAcquire(input, { now: () => FIXED_NOW });
  assert.equal(retry.ok, true);
  assert.equal((await persistedLease(root)).version, 1);
});

test("corrupt bool integers fail closed and legacy epoch advances", async (t) => {
  const root = await workspace(t);
  await mkdir(join(root, "runtime", "goals", "goal-a", "task-leases"), { recursive: true });
  await writeFile(
    leasePath(root),
    JSON.stringify({
      schema_version: "task_lease_v0",
      todo_id: "todo_target",
      owner: "agent-a",
      idempotency_key: "old-key",
      version: true,
      status: "released",
    }),
    "utf8",
  );
  const corrupt = await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });
  assert.equal(corrupt.error_code, "corrupt_lease");

  await writeFile(
    leasePath(root),
    JSON.stringify({
      schema_version: "task_lease_v0",
      todo_id: "todo_target",
      owner: "agent-a",
      idempotency_key: "old-key",
      version: 2,
      status: "released",
    }),
    "utf8",
  );
  const migrated = await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });
  assert.equal(migrated.ok, true);
  assert.equal((await persistedLease(root)).lease_epoch, 2);
});

for (const acquireTtlSeconds of [0, -1]) {
  test(`corrupt acquire TTL '${acquireTtlSeconds}' fails closed`, async (t) => {
    const root = await workspace(t);
    await mkdir(join(root, "runtime", "goals", "goal-a", "task-leases"), {
      recursive: true,
    });
    const existing = {
      schema_version: "task_lease_v0",
      goal_id: "goal-a",
      todo_id: "todo_target",
      owner: "agent-b",
      idempotency_key: "existing-owner",
      write_scopes: ["loopx/**"],
      acquire_ttl_seconds: acquireTtlSeconds,
      version: 1,
      lease_epoch: 1,
      status: "active",
      expires_at: "2030-01-01T00:00:00Z",
    };
    await writeFile(leasePath(root), JSON.stringify(existing), "utf8");

    const result = await executeTaskLeaseAcquire(await request(root), {
      now: () => FIXED_NOW,
    });

    assert.equal(result.error_code, "corrupt_lease");
    assert.deepEqual(result.settlement, {
      effect_id: null,
      receipts: [],
      failure: {
        step: "validation",
        kind: "permission_denied",
        code: "corrupt_lease",
      },
    });
    assert.throws(
      () => leaseInteger(existing, "acquire_ttl_seconds"),
      /acquire_ttl_seconds must be a positive integer/u,
    );
    assert.deepEqual(await persistedLease(root), existing);
  });
}

for (const [label, stored, expected] of [
  ["absent", undefined, null],
  ["null", null, null],
  ["integer", 120, 120],
  ["legacy numeric string", "120", 120],
] as const) {
  test(`persisted acquire TTL ${label} remains compatible`, () => {
    assert.equal(
      leaseInteger({ acquire_ttl_seconds: stored }, "acquire_ttl_seconds"),
      expected,
    );
  });
}

for (const stored of [0, -1, 1.5, true, "invalid", Number.MAX_SAFE_INTEGER + 1]) {
  test(`persisted acquire TTL '${String(stored)}' is corrupt`, () => {
    assert.throws(
      () => leaseInteger({ acquire_ttl_seconds: stored }, "acquire_ttl_seconds"),
      (error: unknown) =>
        error instanceof TaskLeaseAcquireError && error.code === "corrupt_lease",
    );
  });
}

for (const expiresAt of [
  "not-a-timestamp",
  "0",
  "2030-01-01junk",
  "2099-02-30T00:00:00Z",
  "2026-08-26T24:01:00Z",
  "2026-08-26T24:00:00.0000001Z",
]) {
  test(`corrupt active expiration '${expiresAt}' fails closed`, async (t) => {
    const root = await workspace(t);
    await mkdir(join(root, "runtime", "goals", "goal-a", "task-leases"), { recursive: true });
    const existing = {
      schema_version: "task_lease_v0",
      goal_id: "goal-a",
      todo_id: "todo_target",
      owner: "agent-b",
      idempotency_key: "existing-owner",
      write_scopes: ["loopx/**"],
      acquire_ttl_seconds: 120,
      version: 1,
      lease_epoch: 1,
      status: "active",
      expires_at: expiresAt,
    };
    await writeFile(leasePath(root), JSON.stringify(existing), "utf8");

    const result = await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });

    assert.equal(result.error_code, "corrupt_lease");
    assert.deepEqual(await persistedLease(root), existing);
  });
}

for (const { expiresAt, active } of [
  { expiresAt: "2020-01-01", active: false },
  { expiresAt: "2030-01-01", active: true },
  { expiresAt: "0099-01-01T00:00:00Z", active: false },
  { expiresAt: "2026-08-27T02:59:59.123456", active: false },
  { expiresAt: "2026-08-27T02:59:59.123456+00:00", active: false },
  { expiresAt: "2026-08-27T02:59:59.1234567Z", active: false },
  { expiresAt: "2026-08-27T02:59:59.123456789+00:00", active: false },
  { expiresAt: "2026-08-27T03:00:00.123456", active: true },
  { expiresAt: "2026-08-27T03:00:00.123456Z", active: true },
  { expiresAt: "2026-08-27T03:00:00.1234567", active: true },
  { expiresAt: "2026-08-27T03:00:00.123456789Z", active: true },
  { expiresAt: "2026-08-27T03:00:01", active: true },
  { expiresAt: "2026-08-27T03:00:01.1Z", active: true },
  { expiresAt: "2026-08-27T03:00:01.12+00:00", active: true },
  { expiresAt: "2026-08-27T03:00:01.123", active: true },
  { expiresAt: "2026-08-26T24:00:00Z", active: false },
  { expiresAt: "2026-08-26T24:00:00.0000000Z", active: false },
  { expiresAt: "2026-08-27T24:00Z", active: true },
]) {
  test(`valid ${active ? "active" : "expired"} lease timestamp '${expiresAt}' remains compatible`, async (t) => {
    const root = await workspace(t);
    await mkdir(join(root, "runtime", "goals", "goal-a", "task-leases"), { recursive: true });
    const existing = {
      schema_version: "task_lease_v0",
      goal_id: "goal-a",
      todo_id: "todo_target",
      owner: "agent-b",
      idempotency_key: "existing-owner",
      write_scopes: ["loopx/**"],
      acquire_ttl_seconds: 120,
      version: 1,
      lease_epoch: 1,
      status: "active",
      expires_at: expiresAt,
    };
    await writeFile(leasePath(root), JSON.stringify(existing), "utf8");

    const result = await executeTaskLeaseAcquire(await request(root), { now: () => FIXED_NOW });

    if (active) {
      assert.equal(result.error_code, "todo_lease_conflict");
      assert.deepEqual(await persistedLease(root), existing);
    } else {
      assert.equal(result.ok, true);
      assert.equal((await persistedLease(root)).owner, "agent-a");
    }
  });
}
