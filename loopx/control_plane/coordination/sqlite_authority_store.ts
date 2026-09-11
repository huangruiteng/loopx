import { createHash, randomUUID } from "node:crypto";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import type { DatabaseSync } from "node:sqlite";

import type { AuthorityStore, AuthorityStoreCommit, AuthorityStoreCommitResult, AuthorityStoreCommittedTransaction,
  AuthorityStoreIdentityResult, AuthorityStoreLoadResult, AuthorityStoreReadFailure,
  AuthorityStoreReceiptResult, AuthorityStoreScanResult } from "./authority_store.ts";
import { AuthorityStoreProtocolError, canonicalAuthorityBytes, canonicalAuthorityObject,
  canonicalAuthorityObjectList, canonicalAuthoritySha256, normalizeAuthorityStoreCommit,
  parseAuthorityCursor, requireAuthorityStoreId } from "./authority_store_codec.ts";

const SCHEMA = "loopx_sqlite_authority_store_v0";
const IDENTITY = /^sqlite:[0-9a-f]{32}$/;
const REVISION = /^sqlite:([0-9a-f]{32}):([1-9]\d*)$/;
const MAX_SEQUENCE = 9223372036854775807n;
const ROW_COLUMNS = "CAST(cursor AS TEXT) AS sequence, operation_id, commit_digest, projection, events, receipts";
const require = createRequire(import.meta.url);
let qualifiedSqlite: typeof import("node:sqlite") | undefined;

function sqliteDriver(): typeof import("node:sqlite") {
  if (qualifiedSqlite) return qualifiedSqlite;
  let sqlite: typeof import("node:sqlite");
  try { sqlite = require("node:sqlite") as typeof import("node:sqlite"); }
  catch { return protocol("SQLite authority requires a qualified node:sqlite runtime (Node 22.14 or newer recommended)"); }
  // Early experimental drivers defer statement finalization until GC, leaving
  // closed file handles locked on Windows. Probe in memory before touching any
  // authority path; never force GC or hide the leak with cleanup retries.
  const probe = new sqlite.DatabaseSync(":memory:");
  const statement = probe.prepare("SELECT 1");
  probe.close();
  let finalized = false;
  try { statement.get(); }
  catch (error) { finalized = (error as NodeJS.ErrnoException).code === "ERR_INVALID_STATE"; }
  if (!finalized) protocol("SQLite authority requires synchronous statement finalization on close; use Node 22.14 or newer. File authority still supports Node 22.6");
  qualifiedSqlite = sqlite;
  return sqlite;
}

// The retained transactions are also the durable projection outbox consumed by
// scanCommitted. Keeping one row avoids a second copy/ACK authority. Retention
// and compaction are deliberately not part of this provider-conformance slice.
const INSTALL = `
CREATE TABLE metadata (
  singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
  schema_version TEXT NOT NULL, goal_id TEXT NOT NULL, store_identity TEXT NOT NULL
);
CREATE TABLE commits (
  cursor INTEGER PRIMARY KEY CHECK(cursor > 0),
  operation_id TEXT NOT NULL UNIQUE,
  commit_digest TEXT NOT NULL CHECK(length(commit_digest) = 64),
  projection TEXT NOT NULL, events TEXT NOT NULL, receipts TEXT NOT NULL
);
CREATE TABLE head (
  singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
  cursor INTEGER NOT NULL REFERENCES commits(cursor)
);
PRAGMA user_version = 1;
`;

export function sqliteAuthorityPath(directory: string, goalId: string): string {
  requireAuthorityStoreId(goalId, "goal id");
  return join(directory, `authority-${createHash("sha256").update(goalId).digest("hex")}.sqlite`);
}

function protocol(message: string): never { throw new AuthorityStoreProtocolError(message); }

function readFailure(error: unknown): AuthorityStoreReadFailure {
  return error instanceof AuthorityStoreProtocolError || error instanceof SyntaxError
    ? {status: "failed", reason_code: "provider_protocol_violation", reason: error.message}
    : {status: "unavailable", reason_code: "provider_read_unavailable",
      reason: "SQLite authority store could not be read; check database availability and lock contention"};
}

/** One local database per goal. No network filesystem or cross-host authority. */
export class SqliteAuthorityStore implements AuthorityStore {
  readonly path: string;
  readonly goalId: string;
  readonly existingOnly: boolean;
  readonly expectedIdentity: string | undefined;

  constructor(directory: string, goalId: string, options: {existingOnly?: boolean; expectedIdentity?: string} = {}) {
    this.goalId = requireAuthorityStoreId(goalId, "goal id");
    this.path = sqliteAuthorityPath(directory, this.goalId);
    this.existingOnly = options.existingOnly ?? false;
    this.expectedIdentity = options.expectedIdentity;
  }

  private open(write: boolean): DatabaseSync | null {
    const sqlite = sqliteDriver();
    if (!write && !existsSync(this.path)) return null;
    if (write && this.existingOnly && !existsSync(this.path)) protocol("Selected SQLite authority database is missing");
    if (write) mkdirSync(dirname(this.path), {recursive: true, mode: 0o700});
    const db = new sqlite.DatabaseSync(this.path, {readOnly: !write});
    try {
      db.exec("PRAGMA busy_timeout = 5000; PRAGMA foreign_keys = ON;");
      if (write) {
        db.exec("PRAGMA journal_mode = WAL; PRAGMA synchronous = FULL;");
        db.exec("BEGIN IMMEDIATE");
        try {
          const version = db.prepare("PRAGMA user_version").get()?.user_version;
          if (version === 0) {
            // Never adopt an unrelated/unversioned database.
            if (db.prepare("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1").get()) {
              protocol("SQLite database is not an empty LoopX authority database");
            }
            db.exec(INSTALL);
            db.prepare("INSERT INTO metadata VALUES (1, ?, ?, ?)").run(
              SCHEMA, this.goalId, `sqlite:${randomUUID().replaceAll("-", "")}`);
          }
          this.identity(db);
          db.exec("COMMIT");
        } catch (error) { db.exec("ROLLBACK"); throw error; }
      } else this.identity(db);
      return db;
    } catch (error) { db.close(); throw error; }
  }

  private identity(db: DatabaseSync): string {
    if (db.prepare("PRAGMA user_version").get()?.user_version !== 1) {
      protocol("Unsupported SQLite authority schema version; explicit migration is required");
    }
    const row = db.prepare("SELECT * FROM metadata WHERE singleton = 1").get();
    if (!row || row.schema_version !== SCHEMA || row.goal_id !== this.goalId ||
        typeof row.store_identity !== "string" || !IDENTITY.test(row.store_identity) ||
        (this.expectedIdentity !== undefined && row.store_identity !== this.expectedIdentity)) {
      protocol("SQLite authority metadata or goal identity is invalid");
    }
    return row.store_identity;
  }

  private transaction(row: Record<string, unknown>, identity: string): AuthorityStoreCommittedTransaction {
    if (typeof row.sequence !== "string" || !/^[1-9]\d*$/.test(row.sequence)) protocol("Invalid SQLite transaction cursor");
    const cursor = BigInt(row.sequence);
    const projection = canonicalAuthorityObject(JSON.parse(String(row.projection)), "SQLite projection");
    const events = canonicalAuthorityObjectList(JSON.parse(String(row.events)), "SQLite events");
    const receipts = canonicalAuthorityObjectList(JSON.parse(String(row.receipts)), "SQLite receipts");
    const operationId = requireAuthorityStoreId(row.operation_id, "operation id");
    const digest = canonicalAuthoritySha256({
      expected_provider_revision: cursor === 1n ? null : `${identity}:${cursor - 1n}`,
      operation_id: operationId, next_projection: projection, events, receipts,
    });
    if (row.commit_digest !== digest) protocol("SQLite committed row digest mismatch");
    return {cursor: row.sequence, provider_revision: `${identity}:${row.sequence}`,
      operation_id: operationId, projection, events, receipts};
  }

  private current(db: DatabaseSync): AuthorityStoreCommittedTransaction | null {
    const identity = this.identity(db);
    // Positive unique integer cursors are exactly 1..head iff min=1 and
    // count=max=head. SQLite counts the compact covering operation-id index;
    // no retained projection/event/receipt payload is scanned here.
    const bounds = db.prepare(`SELECT
      (SELECT CAST(MIN(cursor) AS TEXT) FROM commits) AS first,
      (SELECT CAST(MAX(cursor) AS TEXT) FROM commits) AS last,
      (SELECT CAST(COUNT(*) AS TEXT) FROM commits) AS count,
      (SELECT CAST(cursor AS TEXT) FROM head WHERE singleton=1) AS head`).get()!;
    if (bounds.count === "0" && bounds.head === null) return null;
    if (bounds.first !== "1" || bounds.last !== bounds.count || bounds.head !== bounds.last) {
      protocol("SQLite head must reference the latest contiguous committed cursor");
    }
    const row = db.prepare(`SELECT ${ROW_COLUMNS} FROM commits WHERE cursor=?`).get(String(bounds.head));
    if (!row) protocol("SQLite head references a missing transaction");
    return this.transaction(row, identity);
  }

  async storeIdentity(): Promise<AuthorityStoreIdentityResult> {
    let db: DatabaseSync | null = null;
    try {
      db = this.open(!this.existingOnly);
      if (!db) return {status: "unavailable", reason_code: "store_identity_unavailable", reason: "SQLite authority database is missing"};
      return {status: "available", store_identity: this.identity(db)};
    }
    catch (error) { return readFailure(error); }
    finally { db?.close(); }
  }

  async loadAuthority(): Promise<AuthorityStoreLoadResult> {
    let db: DatabaseSync | null = null;
    try {
      db = this.open(false);
      if (!db) return {status: "missing"};
      db.exec("BEGIN");
      const current = this.current(db);
      if (current === null) return {status: "missing"};
      return {status: "loaded", cursor: current.cursor, provider_revision: current.provider_revision,
        head: current.projection};
    } catch (error) { return readFailure(error); }
    finally { db?.close(); }
  }

  async commitAuthority(commit: AuthorityStoreCommit): Promise<AuthorityStoreCommitResult> {
    let normalized: AuthorityStoreCommit;
    try {
      normalized = normalizeAuthorityStoreCommit(commit);
      if (normalized.expected_provider_revision !== null && !REVISION.test(normalized.expected_provider_revision)) {
        protocol("Invalid expected SQLite provider revision");
      }
      if (canonicalAuthorityBytes(normalized).byteLength > 16 * 1024 * 1024) {
        return {status: "failed", reason_code: "store_capacity_exhausted", reason: "SQLite commit exceeds 16 MiB"};
      }
    } catch (error) { return {status: "failed", reason_code: "invalid_commit_request",
      reason: error instanceof Error ? error.message : "Invalid commit"}; }
    let db: DatabaseSync | null = null;
    let transactionOpen = false;
    let committing = false;
    try {
      db = this.open(true)!;
      db.exec("BEGIN IMMEDIATE");
      transactionOpen = true;
      const identity = this.identity(db);
      const head = this.current(db);
      const current = head?.cursor ?? null;
      const revision = head?.provider_revision ?? null;
      let conflict: "provider_revision_mismatch" | "operation_id_exists" | null = null;
      if (revision !== normalized.expected_provider_revision) conflict = "provider_revision_mismatch";
      else if (db.prepare("SELECT 1 FROM commits WHERE operation_id = ?").get(normalized.operation_id)) {
        conflict = "operation_id_exists";
      }
      if (conflict) {
        db.exec("ROLLBACK"); transactionOpen = false;
        return {status: "conflict", conflict_kind: conflict, current_provider_revision: revision, current_cursor: current};
      }
      const next = BigInt(current ?? "0") + 1n;
      if (next > MAX_SEQUENCE) protocol("SQLite authority sequence exhausted");
      db.prepare("INSERT INTO commits VALUES (?, ?, ?, ?, ?, ?)").run(next,
        normalized.operation_id, canonicalAuthoritySha256(normalized),
        JSON.stringify(normalized.next_projection), JSON.stringify(normalized.events), JSON.stringify(normalized.receipts));
      db.prepare("INSERT INTO head VALUES (1, ?) ON CONFLICT(singleton) DO UPDATE SET cursor = excluded.cursor").run(next);
      committing = true;
      db.exec("COMMIT"); transactionOpen = false;
      return {status: "applied", provider_revision: `${identity}:${next}`, cursor: String(next)};
    } catch (error) {
      if (transactionOpen) { try { db?.exec("ROLLBACK"); } catch { /* close also abandons the transaction */ } }
      if (committing) return {status: "ambiguous", reason_code: "commit_outcome_unknown",
        reason: "SQLite COMMIT outcome is unknown; reconcile by operation receipt"};
      return {status: "failed", reason_code: error instanceof AuthorityStoreProtocolError || error instanceof SyntaxError
        ? "provider_protocol_violation" : "provider_transaction_failed",
      reason: error instanceof AuthorityStoreProtocolError || error instanceof SyntaxError ? error.message : "SQLite transaction failed before COMMIT"};
    } finally { db?.close(); }
  }

  async readReceipt(operationId: string): Promise<AuthorityStoreReceiptResult> {
    let db: DatabaseSync | null = null;
    try {
      requireAuthorityStoreId(operationId, "operation id");
      db = this.open(false);
      if (!db) return {status: "missing"};
      db.exec("BEGIN");
      const head = this.current(db);
      if (head === null) return {status: "missing"};
      const row = db.prepare(`SELECT ${ROW_COLUMNS} FROM commits WHERE operation_id = ?`).get(operationId);
      if (!row) return {status: "missing"};
      const transaction = this.transaction(row, this.identity(db));
      return {status: "found", cursor: transaction.cursor,
        provider_revision: transaction.provider_revision, receipts: transaction.receipts};
    } catch (error) { return readFailure(error); }
    finally { db?.close(); }
  }

  async scanCommitted(afterCursor: string | null, limit: number): Promise<AuthorityStoreScanResult> {
    let offset: bigint;
    try {
      offset = parseAuthorityCursor(afterCursor);
      if (!Number.isSafeInteger(limit) || limit < 1) protocol("Scan limit must be a positive safe integer");
    } catch (error) { return {status: "failed", reason_code: "invalid_scan_request",
      reason: error instanceof Error ? error.message : "Invalid scan request"}; }
    let db: DatabaseSync | null = null;
    try {
      db = this.open(false);
      if (!db) return {status: "page", transactions: [], next_cursor: afterCursor, has_more: false};
      db.exec("BEGIN");
      const identity = this.identity(db);
      const head = BigInt(this.current(db)?.cursor ?? "0");
      if (offset > head) return {status: "failed", reason_code: "scan_cursor_out_of_range", reason: "Scan cursor is ahead of the provider head"};
      const rows = db.prepare(`SELECT ${ROW_COLUMNS} FROM commits WHERE cursor > ? ORDER BY cursor LIMIT ?`);
      const result = rows.all(offset, BigInt(limit) + 1n);
      // Validate the lookahead row too: it is evidence for has_more.
      const verified = result.map(row => this.transaction(row, identity));
      const transactions = verified.slice(0, limit);
      return {status: "page", transactions, next_cursor: transactions.at(-1)?.cursor ?? afterCursor,
        has_more: result.length > limit};
    } catch (error) { return readFailure(error); }
    finally { db?.close(); }
  }
}
