import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { isAbsolute, join } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import { durableWriteJson, withFileMutationLock } from "../effect_runtime_io.ts";
import type { AuthorityStore } from "./authority_store.ts";
import { isAuthorityJsonObject, requireAuthorityStoreId } from "./authority_store_codec.ts";
import { FileAuthorityStore } from "./file_authority_store.ts";
import { SqliteAuthorityStore, sqliteAuthorityPath } from "./sqlite_authority_store.ts";
import { loadLegacyCoordinationWriterFence } from "./legacy_writer_fence.ts";
import { shadowMaintenanceLockPath } from "./shadow_management.ts";

const SCHEMA = "loopx_local_authority_provider_v0";
type LocalAuthoritySource = "file_v0" | "sqlite_v0";
type ProviderOpenReason =
  | "local_authority_selector_unavailable"
  | "local_authority_selector_invalid"
  | "local_authority_selector_missing"
  | "local_authority_provider_missing"
  | "local_authority_provider_open_failed"
  | "local_authority_provider_identity_mismatch";

/** Null source means selection could not be validated, never a file fallback. */
export class LocalAuthorityProviderOpenError extends Error {
  readonly sourceAuthority: LocalAuthoritySource | null;
  readonly reasonCode: ProviderOpenReason;
  readonly causeReasonCode: string | undefined;

  constructor(source: LocalAuthoritySource | null, code: ProviderOpenReason, reason: string, causeCode?: string) {
    super(reason);
    this.name = "LocalAuthorityProviderOpenError";
    this.sourceAuthority = source;
    this.reasonCode = code;
    this.causeReasonCode = causeCode;
  }
}

/** Shared runtime projection; unrelated request/domain failures keep their contracts. */
export function localAuthorityOpenFailure(error: unknown): Record<string, unknown> {
  if (!(error instanceof LocalAuthorityProviderOpenError)) return {};
  return {source_authority: error.sourceAuthority, reason_code: error.reasonCode, reason: error.message,
    ...(error.causeReasonCode ? {provider_reason_code: error.causeReasonCode} : {}),
    decision_read_from_provider: false, legacy_fallback_used: false};
}
function paths(root: string, goalId: string) {
  if (!isAbsolute(root)) throw new Error("runtime root must be absolute");
  requireAuthorityStoreId(goalId, "goal id");
  return {marker: join(root, "authority", `provider-${createHash("sha256").update(goalId).digest("hex")}.json`),
    sqlite: join(root, "authority", "sqlite-v0"), file: join(root, "authority", "file-v0")};
}

export async function openLocalAuthorityStore(root: string, goalId: string): Promise<AuthorityStore> {
  const p = paths(root, goalId);
  let raw: string;
  try { raw = await readFile(p.marker, "utf8"); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      throw new LocalAuthorityProviderOpenError(null, "local_authority_selector_unavailable", "Local authority provider selector could not be read");
    }
    // Lost selector must never silently redirect an initialized SQLite goal.
    try { await stat(sqliteAuthorityPath(p.sqlite, goalId)); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return new FileAuthorityStore(p.file, goalId);
      throw new LocalAuthorityProviderOpenError(null, "local_authority_selector_unavailable", "Local authority selection could not be resolved");
    }
    throw new LocalAuthorityProviderOpenError(null, "local_authority_selector_missing", "SQLite authority exists but its provider selector is missing");
  }
  let config: unknown;
  try { config = JSON.parse(raw); }
  catch { throw new LocalAuthorityProviderOpenError(null, "local_authority_selector_invalid", "Invalid local authority provider selector JSON"); }
  if (!isAuthorityJsonObject(config) ||
      config.schema_version !== SCHEMA || config.goal_id !== goalId || config.provider !== "sqlite" ||
      typeof config.store_identity !== "string" || !/^sqlite:[0-9a-f]{32}$/.test(config.store_identity)) {
    throw new LocalAuthorityProviderOpenError(null, "local_authority_selector_invalid", "Invalid local authority provider selector");
  }
  try {
    // Validate metadata before comparing selector lineage so drift has its own recovery signal.
    const store = new SqliteAuthorityStore(p.sqlite, goalId, {existingOnly: true});
    // Do not recreate a lost database and thereby silently reset its lineage.
    try { await stat(store.path); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") {
        throw new LocalAuthorityProviderOpenError("sqlite_v0", "local_authority_provider_missing", "Selected SQLite authority database is missing");
      }
      throw new LocalAuthorityProviderOpenError("sqlite_v0", "local_authority_provider_open_failed", "Selected SQLite authority database could not be opened");
    }
    const identity = await store.storeIdentity();
    if (identity.status !== "available") {
      throw new LocalAuthorityProviderOpenError("sqlite_v0", "local_authority_provider_open_failed", identity.reason, identity.reason_code);
    }
    if (identity.store_identity !== config.store_identity) {
      throw new LocalAuthorityProviderOpenError("sqlite_v0", "local_authority_provider_identity_mismatch", "Selected SQLite authority identity changed");
    }
    // Keep every subsequent operation fenced to the selected lineage.
    return new SqliteAuthorityStore(p.sqlite, goalId, {existingOnly: true, expectedIdentity: config.store_identity});
  } catch (error) {
    if (error instanceof LocalAuthorityProviderOpenError) throw error;
    throw new LocalAuthorityProviderOpenError("sqlite_v0", "local_authority_provider_open_failed", "Selected SQLite authority could not be opened");
  }
}

/** Administrative opt-in for an empty, unpromoted goal; no implicit migration. */
export async function selectLocalSqliteAuthority(root: string, goalId: string, execute: boolean) {
  const p = paths(root, goalId);
  return withFileMutationLock(shadowMaintenanceLockPath(root, goalId), async () => {
    if (existsSync(p.marker)) {
      await openLocalAuthorityStore(root, goalId);
      return {ok: true, provider: "sqlite", changed: false, executed: execute};
    }
    const fence = await loadLegacyCoordinationWriterFence(root, goalId);
    if (fence.status !== "missing") throw new Error("Provider selection requires an unpromoted goal without a writer fence");
    const file = new FileAuthorityStore(p.file, goalId, {existingOnly: true});
    if ((await file.loadAuthority()).status !== "missing") throw new Error("Provider selection cannot replace existing file authority");
    const store = new SqliteAuthorityStore(p.sqlite, goalId);
    const existing = await store.loadAuthority();
    if (existing.status === "failed" || existing.status === "unavailable") throw new Error(existing.reason);
    if (existing.status !== "missing") throw new Error("Unselected SQLite authority is not empty");
    if (!execute) return {ok: true, provider: "sqlite", changed: false, executed: false};
    const identity = await store.storeIdentity();
    if (identity.status !== "available") throw new Error(JSON.stringify(identity));
    await durableWriteJson(p.marker, {schema_version: SCHEMA, provider: "sqlite", goal_id: goalId,
      store_identity: identity.store_identity});
    return {ok: true, provider: "sqlite", changed: true, executed: true};
  });
}

// Narrow administrative entrypoint; business writes continue through loopx todo.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const {values} = parseArgs({options: {"runtime-root": {type: "string"}, "goal-id": {type: "string"}, execute: {type: "boolean"}}});
    const result = await selectLocalSqliteAuthority(values["runtime-root"] ?? "", values["goal-id"] ?? "", values.execute === true);
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ok: false, error: error instanceof Error ? error.message : "Provider selection failed",
      ...localAuthorityOpenFailure(error)})}\n`);
    process.exitCode = 1;
  }
}
