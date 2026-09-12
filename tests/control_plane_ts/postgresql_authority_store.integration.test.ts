import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import { Pool, type PoolClient } from "pg";

import {
  DEFAULT_POSTGRESQL_MAX_COMMIT_BYTES,
  installPostgreSqlAuthorityStoreSchema,
  POSTGRESQL_AUTHORITY_STORE_SCHEMA_SQL,
  PostgreSqlAuthorityStore,
  type PostgreSqlAuthorityConnection,
  type PostgreSqlAuthorityDatabase,
} from "../../loopx/control_plane/coordination/postgresql_authority_store.ts";
import {
  authorityStoreCommitFixture as commit,
  registerAuthorityStoreConformance,
} from "./authority_store_conformance.ts";

const connectionString = process.env.LOOPX_TEST_POSTGRES_URL;
const pool = connectionString ? new Pool({ connectionString, max: 12 }) : null;
const STORE_IDENTITY = `postgresql:${"b".repeat(32)}`;
const TENANT_SCOPED_TABLES = [
  "authority_heads",
  "authority_commits",
  "authority_events",
  "authority_receipts",
] as const;

function wrapClient(client: PoolClient): PostgreSqlAuthorityConnection {
  return {
    query: async (text, values) => await client.query(text, values ? [...values] : undefined),
    release: (error) => client.release(error),
  };
}

function databaseFromPool(value: Pool): PostgreSqlAuthorityDatabase {
  return { connect: async () => wrapClient(await value.connect()) };
}

function quotedRole(role: string): string {
  assert.match(role, /^[a-z][a-z0-9_]+$/);
  return `"${role}"`;
}

async function createRuntimeRole(role: string): Promise<void> {
  const identifier = quotedRole(role);
  await pool!.query(`CREATE ROLE ${identifier} NOLOGIN`);
  await pool!.query(`GRANT USAGE ON SCHEMA loopx_control_plane TO ${identifier}`);
  await pool!.query(
    `GRANT SELECT ON loopx_control_plane.authority_store_metadata TO ${identifier}`,
  );
  await pool!.query(
    `GRANT SELECT, INSERT, UPDATE ON loopx_control_plane.authority_heads TO ${identifier}`,
  );
  await pool!.query(
    `GRANT SELECT, INSERT ON loopx_control_plane.authority_commits,
       loopx_control_plane.authority_events,
       loopx_control_plane.authority_receipts TO ${identifier}`,
  );
}

function databaseForRuntimeRole(value: Pool, role: string): PostgreSqlAuthorityDatabase {
  const identifier = quotedRole(role);
  return {
    connect: async () => {
      const client = await value.connect();
      await client.query("RESET ROLE");
      await client.query(`SET ROLE ${identifier}`);
      return {
        query: async (text, values) =>
          await client.query(text, values ? [...values] : undefined),
        release: async (error) => {
          try {
            await client.query("RESET ROLE");
            client.release(error);
          } catch (resetError) {
            client.release(resetError as Error);
          }
        },
      };
    },
  };
}

async function queryAsRuntimeRole(
  value: Pool,
  role: string,
  operation: (client: PoolClient) => Promise<void>,
): Promise<void> {
  const client = await value.connect();
  try {
    await client.query(`SET ROLE ${quotedRole(role)}`);
    await operation(client);
  } finally {
    await client.query("RESET ROLE");
    client.release();
  }
}

const database = pool ? databaseFromPool(pool) : null;
const installed = database
  ? installPostgreSqlAuthorityStoreSchema(database, STORE_IDENTITY)
  : null;

async function cleanScope(tenantId: string, goalId: string): Promise<void> {
  if (!pool) return;
  await pool.query(
    `DELETE FROM loopx_control_plane.authority_heads
     WHERE tenant_id = $1 AND goal_id = $2`,
    [tenantId, goalId],
  );
}

if (database && installed) {
  registerAuthorityStoreConformance("PostgreSQL provider", async (t) => {
    await installed;
    const tenantId = `tenant-${randomUUID()}`;
    const goalId = `goal-${randomUUID()}`;
    t.after(() => cleanScope(tenantId, goalId));
    return {
      store: new PostgreSqlAuthorityStore(database, {
        tenant_id: tenantId,
        goal_id: goalId,
      }),
      contender: new PostgreSqlAuthorityStore(database, {
        tenant_id: tenantId,
        goal_id: goalId,
      }),
    };
  });

  test("PostgreSQL scan binds head and rows to one snapshot during concurrent commit", async t => {
    await installed;
    const options = {tenant_id: `tenant-${randomUUID()}`, goal_id: `goal-${randomUUID()}`};
    t.after(() => cleanScope(options.tenant_id, options.goal_id));
    const writer = new PostgreSqlAuthorityStore(database, options);
    const first = await writer.commitAuthority(commit(null, "snapshot-first", 1, 1));
    assert.equal(first.status, "applied");
    if (first.status !== "applied") return;
    let interleaved = false;
    const reader = new PostgreSqlAuthorityStore({connect: async () => {
      const connection = await database.connect();
      return {...connection, query: async (sql, values) => {
        const result = await connection.query(sql, values);
        if (!interleaved && sql.includes("FROM loopx_control_plane.authority_heads")) {
          interleaved = true;
          assert.equal((await writer.commitAuthority(commit(first.provider_revision,
            "snapshot-second", 2, 2))).status, "applied");
        }
        return result;
      }};
    }}, options);
    const page = await reader.scanCommitted(null, 10);
    assert.equal(interleaved, true);
    assert.equal(page.status, "page", JSON.stringify(page));
    if (page.status !== "page") return;
    assert.deepEqual(page.transactions.map(row => row.operation_id), ["snapshot-first"]);
    assert.equal(page.has_more, false);
    const next = await reader.scanCommitted(page.next_cursor, 10);
    assert.equal(next.status, "page");
    if (next.status === "page") assert.deepEqual(next.transactions.map(row => row.operation_id), ["snapshot-second"]);
  });

  for (const removedCursor of [2, 3]) {
    test(`PostgreSQL scan rejects a missing retained row at cursor ${removedCursor}`, async t => {
      await installed;
      const options = {tenant_id: `tenant-${randomUUID()}`, goal_id: `goal-${randomUUID()}`};
      t.after(() => cleanScope(options.tenant_id, options.goal_id));
      const store = new PostgreSqlAuthorityStore(database, options);
      let revision: string | null = null;
      for (let index = 1; index <= 3; index++) {
        const result = await store.commitAuthority(commit(revision, `gap-${index}`, index, index));
        assert.equal(result.status, "applied");
        if (result.status !== "applied") return;
        revision = result.provider_revision;
      }
      await pool!.query("DELETE FROM loopx_control_plane.authority_commits WHERE tenant_id=$1 AND goal_id=$2 AND cursor=$3",
        [options.tenant_id, options.goal_id, removedCursor]);
      for (const limit of [1, 10]) {
        const result = await store.scanCommitted(removedCursor === 3 ? "1" : null, limit);
        assert.equal(result.status, "failed", JSON.stringify(result));
        if (result.status === "failed") assert.equal(result.reason_code, "provider_protocol_violation");
      }
      const head = await store.loadAuthority();
      assert.equal(head.status, "loaded");
      if (head.status === "loaded") assert.equal(head.provider_revision, revision);
    });
  }

  test("PostgreSQL provider scopes identical goals and operations by tenant", async (t) => {
    await installed;
    const goalId = `goal-${randomUUID()}`;
    const firstTenant = `tenant-${randomUUID()}`;
    const secondTenant = `tenant-${randomUUID()}`;
    t.after(async () => {
      await cleanScope(firstTenant, goalId);
      await cleanScope(secondTenant, goalId);
    });
    const first = new PostgreSqlAuthorityStore(database, {
      tenant_id: firstTenant,
      goal_id: goalId,
    });
    const second = new PostgreSqlAuthorityStore(database, {
      tenant_id: secondTenant,
      goal_id: goalId,
    });

    const results = await Promise.all([
      first.commitAuthority(commit(null, "shared-operation", 1, 1)),
      second.commitAuthority(commit(null, "shared-operation", 1, 1)),
    ]);
    assert.deepEqual(results.map((result) => result.status), ["applied", "applied"]);
    assert.equal((await first.readReceipt("shared-operation")).status, "found");
    assert.equal((await second.readReceipt("shared-operation")).status, "found");
  });

  test("PostgreSQL provider rolls back head, events, and receipts together", async (t) => {
    await installed;
    const tenantId = `tenant-${randomUUID()}`;
    const goalId = `goal-${randomUUID()}`;
    t.after(async () => {
      await pool!.query(
        "DROP TRIGGER IF EXISTS authority_commit_test_failure ON loopx_control_plane.authority_commits",
      );
      await pool!.query(
        "DROP FUNCTION IF EXISTS loopx_control_plane.reject_test_authority_commit()",
      );
      await cleanScope(tenantId, goalId);
    });
    await pool!.query(`
      CREATE OR REPLACE FUNCTION loopx_control_plane.reject_test_authority_commit()
      RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.operation_id = 'force-rollback' THEN
          RAISE EXCEPTION 'injected transaction failure';
        END IF;
        RETURN NEW;
      END;
      $$
    `);
    await pool!.query(`
      CREATE TRIGGER authority_commit_test_failure
      BEFORE INSERT ON loopx_control_plane.authority_commits
      FOR EACH ROW EXECUTE FUNCTION loopx_control_plane.reject_test_authority_commit()
    `);
    const store = new PostgreSqlAuthorityStore(database, {
      tenant_id: tenantId,
      goal_id: goalId,
    });
    const result = await store.commitAuthority(commit(null, "force-rollback", 1, 1));
    assert.equal(result.status, "failed");
    assert.deepEqual(await store.loadAuthority(), { status: "missing" });
    assert.deepEqual(await store.readReceipt("force-rollback"), { status: "missing" });
  });

  test("PostgreSQL COMMIT response loss is ambiguous and receipt-recoverable", async (t) => {
    await installed;
    const tenantId = `tenant-${randomUUID()}`;
    const goalId = `goal-${randomUUID()}`;
    t.after(() => cleanScope(tenantId, goalId));
    let loseCommitResponse = true;
    const lossyDatabase: PostgreSqlAuthorityDatabase = {
      connect: async () => {
        const client = await pool!.connect();
        return {
          query: async (text, values) => {
            const result = await client.query(text, values ? [...values] : undefined);
            if (text === "COMMIT" && loseCommitResponse) {
              loseCommitResponse = false;
              throw new Error("simulated response loss after PostgreSQL commit");
            }
            return result;
          },
          release: (error) => client.release(error),
        };
      },
    };
    const store = new PostgreSqlAuthorityStore(lossyDatabase, {
      tenant_id: tenantId,
      goal_id: goalId,
    });
    const result = await store.commitAuthority(commit(null, "operation-ambiguous", 1, 4));
    assert.equal(result.status, "ambiguous");
    const receipt = await store.readReceipt("operation-ambiguous");
    assert.equal(receipt.status, "found");
    if (receipt.status === "found") assert.equal(receipt.receipts[0]?.lease_epoch, 4);
    const loaded = await store.loadAuthority();
    assert.equal(loaded.status, "loaded");
  });

  test("PostgreSQL database incarnation binds revisions and cannot be rebound", async (t) => {
    await installed;
    const tenantId = `tenant-${randomUUID()}`;
    const goalId = `goal-${randomUUID()}`;
    t.after(() => cleanScope(tenantId, goalId));
    const store = new PostgreSqlAuthorityStore(database, {
      tenant_id: tenantId,
      goal_id: goalId,
    });
    const first = await store.commitAuthority(commit(null, "operation-a", 1, 1));
    assert.equal(first.status, "applied");
    if (first.status !== "applied") return;
    const foreignRevision = first.provider_revision.replace(
      STORE_IDENTITY,
      `postgresql:${"c".repeat(32)}`,
    );
    const crossLineage = await store.commitAuthority(
      commit(foreignRevision, "operation-b", 2, 2),
    );
    assert.equal(crossLineage.status, "conflict");
    assert.equal((await store.readReceipt("operation-b")).status, "missing");

    await assert.rejects(
      installPostgreSqlAuthorityStoreSchema(
        database,
        `postgresql:${"c".repeat(32)}`,
      ),
      /database incarnation/,
    );
  });

  test("PostgreSQL runtime role is confined by transaction-local tenant RLS", async (t) => {
    await installed;
    const role = `loopx_test_runtime_${randomUUID().replaceAll("-", "")}`;
    const firstTenant = `tenant-${randomUUID()}`;
    const secondTenant = `tenant-${randomUUID()}`;
    const goalId = `goal-${randomUUID()}`;
    const runtimePool = new Pool({ connectionString, max: 1 });
    await createRuntimeRole(role);
    t.after(async () => {
      await runtimePool.end();
      await cleanScope(firstTenant, goalId);
      await cleanScope(secondTenant, goalId);
      await pool!.query(`DROP OWNED BY ${quotedRole(role)}`);
      await pool!.query(`DROP ROLE ${quotedRole(role)}`);
    });

    const runtimeDatabase = databaseForRuntimeRole(runtimePool, role);
    const first = new PostgreSqlAuthorityStore(runtimeDatabase, {
      tenant_id: firstTenant,
      goal_id: goalId,
    });
    const second = new PostgreSqlAuthorityStore(runtimeDatabase, {
      tenant_id: secondTenant,
      goal_id: goalId,
    });
    assert.equal((await first.commitAuthority(commit(null, "operation-a", 1, 1))).status, "applied");
    assert.equal((await second.commitAuthority(commit(null, "operation-b", 1, 1))).status, "applied");
    assert.equal((await first.loadAuthority()).status, "loaded");
    assert.equal((await second.readReceipt("operation-b")).status, "found");

    await queryAsRuntimeRole(runtimePool, role, async (client) => {
      for (const table of TENANT_SCOPED_TABLES) {
        const unscoped = await client.query(
          `SELECT tenant_id FROM loopx_control_plane.${table}`,
        );
        assert.equal(unscoped.rowCount, 0, `${table} must fail closed without tenant context`);
      }

      await client.query("BEGIN READ ONLY");
      await client.query(
        "SELECT set_config('loopx.tenant_id', $1, TRUE)",
        [firstTenant],
      );
      for (const table of TENANT_SCOPED_TABLES) {
        const scoped = await client.query(
          `SELECT DISTINCT tenant_id FROM loopx_control_plane.${table}`,
        );
        assert.deepEqual(scoped.rows, [{ tenant_id: firstTenant }]);
      }
      await client.query("ROLLBACK");

      await client.query("BEGIN");
      await client.query(
        "SELECT set_config('loopx.tenant_id', $1, TRUE)",
        [firstTenant],
      );
      await assert.rejects(
        client.query(
          `INSERT INTO loopx_control_plane.authority_heads
             (tenant_id, goal_id, provider_revision, cursor, head)
           VALUES ($1, $2, 0, 0, NULL)`,
          [secondTenant, `forbidden-${randomUUID()}`],
        ),
        /row-level security policy/,
      );
      await client.query("ROLLBACK");

      await assert.rejects(
        client.query(
          `UPDATE loopx_control_plane.authority_store_metadata
           SET store_identity = $1 WHERE singleton = TRUE`,
          [`postgresql:${"d".repeat(32)}`],
        ),
        /permission denied/,
      );
    });
  });
} else {
  test("PostgreSQL authority-store integration (set LOOPX_TEST_POSTGRES_URL)", { skip: true }, () => {});
}

test.after(async () => {
  await pool?.end();
});

test("PostgreSQL schema declares fail-closed tenant RLS on every scoped table", () => {
  for (const table of TENANT_SCOPED_TABLES) {
    assert.match(
      POSTGRESQL_AUTHORITY_STORE_SCHEMA_SQL,
      new RegExp(`ALTER TABLE loopx_control_plane\\.${table} FORCE ROW LEVEL SECURITY`),
    );
    assert.match(
      POSTGRESQL_AUTHORITY_STORE_SCHEMA_SQL,
      new RegExp(`CREATE POLICY ${table}_tenant_scope`),
    );
  }
  assert.match(
    POSTGRESQL_AUTHORITY_STORE_SCHEMA_SQL,
    /current_setting\('loopx\.tenant_id', TRUE\)/,
  );
});

test("PostgreSQL provider rejects an oversized commit before opening a connection", async () => {
  let connectionAttempts = 0;
  const disconnectedDatabase: PostgreSqlAuthorityDatabase = {
    connect: async () => {
      connectionAttempts += 1;
      throw new Error("capacity admission must run before connect");
    },
  };
  const store = new PostgreSqlAuthorityStore(disconnectedDatabase, {
    tenant_id: "tenant-capacity",
    goal_id: "goal-capacity",
    max_commit_bytes: 256,
  });
  const oversized = commit(null, "operation-oversized", 1, 1);
  oversized.next_projection.payload = "x".repeat(1024);

  const result = await store.commitAuthority(oversized);
  assert.equal(result.status, "failed");
  if (result.status === "failed") {
    assert.equal(result.reason_code, "store_capacity_exhausted");
    assert.match(result.reason, /configured maximum is 256/);
  }
  assert.equal(connectionAttempts, 0);
});

test("PostgreSQL provider validates its commit capacity envelope", () => {
  const disconnectedDatabase: PostgreSqlAuthorityDatabase = {
    connect: async () => {
      throw new Error("not reached");
    },
  };
  const defaultStore = new PostgreSqlAuthorityStore(disconnectedDatabase, {
    tenant_id: "tenant-capacity",
    goal_id: "goal-capacity",
  });
  assert.equal(defaultStore.maxCommitBytes, DEFAULT_POSTGRESQL_MAX_COMMIT_BYTES);
  assert.throws(
    () => new PostgreSqlAuthorityStore(disconnectedDatabase, {
      tenant_id: "tenant-capacity",
      goal_id: "goal-capacity",
      max_commit_bytes: 0,
    }),
    /max commit bytes must be a positive safe integer/,
  );
});

test("PostgreSQL provider evicts and awaits cleanup-uncertain read connections", async () => {
  const tenantId = "tenant-cleanup-fault";
  const rollbackFailure = new Error("injected rollback failure");
  const queries: string[] = [];
  let finishRelease: (() => void) | undefined;
  let resultSettled = false;
  const releaseGate = new Promise<void>((resolve) => {
    finishRelease = resolve;
  });
  let reportRelease: ((error: Error | undefined) => void) | undefined;
  const releaseStarted = new Promise<Error | undefined>((resolve) => {
    reportRelease = resolve;
  });
  const faultingDatabase: PostgreSqlAuthorityDatabase = {
    connect: async () => ({
      query: async (text) => {
        queries.push(text);
        if (text === "ROLLBACK") throw rollbackFailure;
        if (text.includes("set_config")) {
          return { rows: [{ tenant_id: tenantId }], rowCount: 1 };
        }
        if (text.includes("authority_store_metadata")) {
          return {
            rows: [{ schema_version: "loopx_postgresql_authority_store_v0", store_identity: STORE_IDENTITY }],
            rowCount: 1,
          };
        }
        if (text.includes("authority_heads")) {
          return { rows: [], rowCount: 0 };
        }
        return { rows: [], rowCount: 0 };
      },
      release: async (error) => {
        reportRelease?.(error);
        await releaseGate;
      },
    }),
  };
  const store = new PostgreSqlAuthorityStore(faultingDatabase, {
    tenant_id: tenantId,
    goal_id: "goal-cleanup-fault",
  });

  const resultPromise = store.loadAuthority().then((result) => {
    resultSettled = true;
    return result;
  });
  assert.strictEqual(await releaseStarted, rollbackFailure);
  assert.equal(resultSettled, false, "read result must wait for asynchronous connection eviction");
  assert.ok(finishRelease);
  finishRelease();

  assert.deepEqual(await resultPromise, {
    status: "unavailable",
    reason_code: "provider_read_unavailable",
    reason: "PostgreSQL authority store is unavailable",
  });
  assert.equal(queries.filter((query) => query === "ROLLBACK").length, 1);
});
