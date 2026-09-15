/**
 * Explicit V1 to V2 migration for the SQLite authority provider.
 *
 * V1 retained a full projection inside every committed row. V2 keeps the same
 * commits, operation identity, receipts, ordering and commit proofs, and
 * replaces that per-row projection copy with one checkpoint per bounded window
 * plus one exact delta per commit. Authority membership, replay and projection
 * delivery do not change; only redundant storage does.
 *
 * The migration is linear, transactional and idempotent: it reads the frozen
 * V1 rows, proves every stored digest while writing the V2 log, proves that
 * every written delta reconstructs the exact projection it claims (the V2 read
 * contract, checked before the swap instead of after the first read), verifies
 * that the retained transaction identity sequence is byte-identical, and only
 * then swaps tables inside the same transaction. A V1 database that never
 * committed migrates to an equally empty V2 database; nothing is invented. Any
 * failure leaves the V1 database untouched. A production first-cutover command,
 * migration manifest and reverse export remain separate reviewed deliverables.
 */
import { createHash } from "node:crypto";
import { existsSync, statSync } from "node:fs";
import type { DatabaseSync } from "node:sqlite";

import type { JsonObject } from "../effect_program.ts";
import { AuthorityStoreProtocolError, canonicalAuthorityObject,
  canonicalAuthorityObjectList, requireAuthorityStoreId } from "./authority_store_codec.ts";
import { authorityStateCheckpointCursor, authorityStateDelta, authorityStateDeltaReconstructs,
  authorityStateDigest, isAuthorityStateCheckpoint } from "./authority_state_log.ts";
import {
  SQLITE_AUTHORITY_STORE_SCHEMA,
  commitDigest,
  sqliteAuthorityPath,
  sqliteAuthorityStoreSchemaDdl,
} from "./sqlite_authority_store.ts";
import {sqliteAuthorityRuntime} from "./sqlite_runtime.ts";

export const SQLITE_AUTHORITY_STORE_V1_SCHEMA = "loopx_sqlite_authority_store_v0";
const IDENTITY = /^sqlite:[0-9a-f]{32}$/;
const MIGRATION_PAGE = 512;

export type SqliteAuthorityMigrationStatus = "planned" | "migrated" | "already_current" | "missing" | "failed";

export interface SqliteAuthorityMigrationResult {
  schema_version: "loopx_sqlite_authority_migration_v0";
  status: SqliteAuthorityMigrationStatus;
  database_path?: string;
  commits?: number;
  checkpoints?: number;
  sequence_digest?: string;
  identity?: string;
  database_bytes_before?: number;
  database_bytes_after?: number;
  reason_code?: string;
  reason?: string;
}

interface SqliteAuthorityMigrationInspection {
  version: number;
  schema_version: string;
  goal_id: string;
  identity: string;
  commits: number;
}

/**
 * Migrate one V1 authority database in place.
 *
 * `execute` must be set explicitly; without it the call only reports that this
 * database needs the migration. The goal id binds the expected lineage, so a
 * database belonging to another goal is never rewritten.
 */
export function migrateSqliteAuthorityStoreV1ToV2(
  directory: string,
  goalId: string,
  options: {execute?: boolean; expectedIdentity?: string} = {},
): SqliteAuthorityMigrationResult {
  const path = sqliteAuthorityPath(directory, goalId);
  const base: SqliteAuthorityMigrationResult = {schema_version: "loopx_sqlite_authority_migration_v0", status: "failed"};
  if (!existsSync(path)) {
    return {...base, status: "missing", reason_code: "migration_source_missing",
      reason: "SQLite authority database is missing"};
  }
  const before = statSync(path).size;
  const inspection = inspectSqliteAuthorityStore(path, goalId, options.expectedIdentity);
  if (!inspection.ok) {
    return {...base, reason_code: inspection.reason_code, reason: inspection.reason,
      database_bytes_before: before};
  }
  if (inspection.value.version === 2) {
    return {...base, status: "already_current", database_path: path, identity: inspection.value.identity,
      commits: inspection.value.commits, database_bytes_before: before, database_bytes_after: before};
  }
  if (inspection.value.version !== 1) {
    return {...base, reason_code: "migration_version_unsupported",
      reason: "SQLite authority database is not a migrated V1 authority store",
      database_bytes_before: before};
  }
  if (!options.execute) {
    return {...base, status: "planned", database_path: path, identity: inspection.value.identity,
      commits: inspection.value.commits, database_bytes_before: before};
  }
  return executeSqliteAuthorityMigration(path, goalId, inspection.value, before);
}

function inspectSqliteAuthorityStore(
  path: string,
  goalId: string,
  expectedIdentity: string | undefined,
): {ok: true; value: SqliteAuthorityMigrationInspection} | {ok: false; reason_code: string; reason: string} {
  const {driver: sqlite} = sqliteAuthorityRuntime();
  let db: DatabaseSync | null = null;
  try {
    db = new sqlite.DatabaseSync(path, {readOnly: true});
    const version = Number(db.prepare("PRAGMA user_version").get()?.user_version ?? 0);
    const metadata = db.prepare("SELECT * FROM metadata WHERE singleton = 1").get();
    if (metadata === undefined || metadata === null || typeof metadata.store_identity !== "string" ||
        !IDENTITY.test(metadata.store_identity) || metadata.goal_id !== goalId ||
        (expectedIdentity !== undefined && metadata.store_identity !== expectedIdentity) ||
        (metadata.schema_version !== SQLITE_AUTHORITY_STORE_SCHEMA &&
          metadata.schema_version !== SQLITE_AUTHORITY_STORE_V1_SCHEMA)) {
      throw new AuthorityStoreProtocolError("SQLite authority metadata or goal identity is invalid");
    }
    if (version === 1 || version === 2) {
      const bounds = db.prepare(`SELECT
        (SELECT CAST(MIN(cursor) AS TEXT) FROM commits) AS first,
        (SELECT CAST(MAX(cursor) AS TEXT) FROM commits) AS last,
        CAST((SELECT COUNT(*) FROM commits) AS TEXT) AS count,
        (SELECT CAST(cursor AS TEXT) FROM head WHERE singleton=1) AS head`).get()!;
      if (!(bounds.count === "0" && bounds.head === null) &&
        (bounds.first !== "1" || bounds.last !== bounds.count || bounds.head !== bounds.last)) {
        throw new AuthorityStoreProtocolError("SQLite authority store is not a contiguous committed lineage");
      }
      return {ok: true, value: {version, schema_version: metadata.schema_version as string, goal_id: goalId,
        identity: metadata.store_identity, commits: Number(bounds.count)}};
    }
    return {ok: false, reason_code: "migration_version_unsupported",
      reason: "SQLite authority database is not a migrated V1 authority store"};
  } catch (error) {
    return {ok: false, reason_code: error instanceof AuthorityStoreProtocolError || error instanceof SyntaxError
      ? "migration_protocol_violation" : "migration_source_unavailable",
    reason: error instanceof Error ? error.message : "SQLite authority migration inspection failed"};
  } finally { db?.close(); }
}

function executeSqliteAuthorityMigration(
  path: string,
  goalId: string,
  inspection: SqliteAuthorityMigrationInspection,
  before: number,
): SqliteAuthorityMigrationResult {
  const base: SqliteAuthorityMigrationResult = {schema_version: "loopx_sqlite_authority_migration_v0", status: "failed"};
  const {driver: sqlite} = sqliteAuthorityRuntime();
  let db: DatabaseSync | null = null;
  let transactionOpen = false;
  try {
    db = new sqlite.DatabaseSync(path);
    db.exec("PRAGMA busy_timeout = 5000; PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA synchronous = FULL;");
    db.exec("BEGIN IMMEDIATE");
    transactionOpen = true;
    const metadata = db.prepare("SELECT * FROM metadata WHERE singleton = 1").get();
    if (metadata === undefined || metadata === null || metadata.store_identity !== inspection.identity ||
        metadata.goal_id !== goalId ||
        Number(db.prepare("PRAGMA user_version").get()?.user_version ?? 0) !== 1 || metadata.schema_version !==
        SQLITE_AUTHORITY_STORE_V1_SCHEMA) {
      throw new AuthorityStoreProtocolError("SQLite authority store changed before its migration started");
    }
    db.exec(sqliteAuthorityStoreSchemaDdl({commits: "commits_v2", checkpoints: "checkpoints_v2", head: "head_v2"}));
    const insertCommit = db.prepare("INSERT INTO commits_v2 VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
    const insertCheckpoint = db.prepare("INSERT INTO checkpoints_v2 VALUES (?, ?, ?)");
    const identityDigest = createHash("sha256");
    let previous: JsonObject | null = null;
    let previousDigest: string | null = null;
    let cursor = 0n;
    let commits = 0;
    let checkpoints = 0;
    for (;;) {
      const rows = db.prepare(`SELECT CAST(cursor AS TEXT) AS sequence, operation_id, commit_digest,
          projection, events, receipts FROM commits WHERE cursor > ? ORDER BY cursor LIMIT ?`)
        .all(cursor.toString(), BigInt(MIGRATION_PAGE)) as unknown as Record<string, unknown>[];
      if (rows.length === 0) break;
      for (const row of rows) {
        const sequence = row.sequence;
        if (typeof sequence !== "string" || !/^[1-9]\d*$/.test(sequence)) {
          throw new AuthorityStoreProtocolError("V1 authority store cursor is invalid");
        }
        cursor = BigInt(sequence);
        const operationId = requireAuthorityStoreId(row.operation_id, "operation id");
        const projection = canonicalAuthorityObject(
          JSON.parse(String(row.projection)) as unknown, "V1 authority projection");
        const events = canonicalAuthorityObjectList(JSON.parse(String(row.events)) as unknown, "V1 authority events");
        const receipts = canonicalAuthorityObjectList(JSON.parse(String(row.receipts)) as unknown, "V1 authority receipts");
        if (row.commit_digest !== commitDigest(inspection.identity, cursor, operationId, projection, events, receipts)) {
          throw new AuthorityStoreProtocolError("V1 authority commit digest mismatch");
        }
        const stateDigest = authorityStateDigest(projection);
        const delta = authorityStateDelta(previous ?? {}, projection);
        // The committed V1 projection is the contract the migrated store must
        // keep readable, so the delta is proved against it here. A codec that
        // cannot address one of its keys must fail the migration and leave V1
        // intact instead of publishing a log the V2 read path rejects.
        if (!authorityStateDeltaReconstructs(previous ?? {}, delta, projection)) {
          throw new AuthorityStoreProtocolError(
            "V1 authority state delta does not reconstruct its commit");
        }
        if (isAuthorityStateCheckpoint(cursor)) {
          insertCheckpoint.run(cursor.toString(), JSON.stringify(projection), stateDigest);
          checkpoints += 1;
        }
        insertCommit.run(cursor.toString(), operationId, row.commit_digest, stateDigest, previousDigest,
          JSON.stringify(delta), JSON.stringify(events), JSON.stringify(receipts));
        identityDigest.update(`${cursor.toString()}\u0000${operationId}\u0000${String(row.commit_digest)}\n`);
        previous = projection;
        previousDigest = stateDigest;
        commits += 1;
      }
    }
    if (commits !== inspection.commits) {
      throw new AuthorityStoreProtocolError("V1 authority store changed while it was migrated");
    }
    // A version-1 database that only published its schema and metadata has no
    // committed projection to re-publish, so version 2 stays empty as well
    // instead of inventing a head the goal never committed.
    if (previous !== null && previousDigest !== null) {
      db.prepare("INSERT INTO head_v2 VALUES (1, ?, ?, ?)").run(cursor.toString(),
        JSON.stringify(previous), previousDigest);
    }
    // Swap only after every retained row was proved and re-published.
    db.exec("DROP TABLE head");
    db.exec("DROP TABLE commits");
    db.exec("ALTER TABLE commits_v2 RENAME TO commits");
    db.exec("ALTER TABLE checkpoints_v2 RENAME TO checkpoints");
    db.exec("ALTER TABLE head_v2 RENAME TO head");
    db.prepare("UPDATE metadata SET schema_version = ? WHERE singleton = 1").run(SQLITE_AUTHORITY_STORE_SCHEMA);
    db.exec("PRAGMA user_version = 2");
    db.exec("COMMIT");
    transactionOpen = false;
    const sequenceDigest = identityDigest.digest("hex");
    const verification = verifyMigratedStore(path, goalId, inspection.identity, sequenceDigest);
    if (verification !== null) {
      return {...base, reason_code: verification.reason_code, reason: verification.reason,
        database_bytes_before: before};
    }
    return {schema_version: "loopx_sqlite_authority_migration_v0", status: "migrated",
      database_path: path, commits, checkpoints, sequence_digest: sequenceDigest,
      identity: inspection.identity, database_bytes_before: before,
      database_bytes_after: statSync(path).size};
  } catch (error) {
    if (transactionOpen) { try { db?.exec("ROLLBACK"); } catch { /* close also abandons the transaction */ } }
    return {...base, reason_code: error instanceof AuthorityStoreProtocolError || error instanceof SyntaxError
      ? "migration_protocol_violation" : "migration_transaction_failed",
    reason: error instanceof Error ? error.message : "SQLite authority migration failed",
    database_bytes_before: before};
  } finally { db?.close(); }
}

/**
 * Read the migrated store back and prove that its retained transaction
 * identity sequence and authority lineage are exactly the pre-migration ones.
 */
function verifyMigratedStore(
  path: string,
  goalId: string,
  identity: string,
  expectedSequenceDigest: string,
): {reason_code: string; reason: string} | null {
  const {driver: sqlite} = sqliteAuthorityRuntime();
  const db = new sqlite.DatabaseSync(path, {readOnly: true});
  try {
    const digest = createHash("sha256");
    const rows = db.prepare(`SELECT CAST(cursor AS TEXT) AS sequence, operation_id, commit_digest
      FROM commits ORDER BY cursor`).all() as unknown as Record<string, unknown>[];
    for (const row of rows) {
      digest.update(`${String(row.sequence)}\u0000${String(row.operation_id)}\u0000${String(row.commit_digest)}\n`);
    }
    if (digest.digest("hex") !== expectedSequenceDigest) {
      return {reason_code: "migration_sequence_changed",
        reason: "migrated store changed the retained transaction identity sequence"};
    }
    const metadata = db.prepare("SELECT goal_id, store_identity, schema_version FROM metadata WHERE singleton = 1").get();
    if (metadata?.goal_id !== goalId || metadata.store_identity !== identity ||
        metadata.schema_version !== SQLITE_AUTHORITY_STORE_SCHEMA) {
      return {reason_code: "migration_identity_changed",
        reason: "migrated store changed the authority lineage"};
    }
    return null;
  } finally { db.close(); }
}
