import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { isAbsolute, join } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import { durableWriteJson, withFileMutationLock } from "../effect_runtime_io.ts";
import {
  authorityStoreSourceAuthority,
  type AuthorityStore,
  type AuthorityStoreProviderKind,
  type AuthorityStoreSourceAuthority,
} from "./authority_store.ts";
import { hasExactAuthorityKeys, isAuthorityJsonObject, requireAuthorityStoreId } from "./authority_store_codec.ts";
import { FileAuthorityStore } from "./file_authority_store.ts";
import { SqliteAuthorityStore, sqliteAuthorityPath } from "./sqlite_authority_store.ts";
import { loadLegacyCoordinationWriterFence } from "./legacy_writer_fence.ts";
import { shadowMaintenanceLockPath } from "./shadow_management.ts";

const SCHEMA = "loopx_local_authority_provider_v0";
export const DEFAULT_LOCAL_AUTHORITY_PROVIDER = "file" as const satisfies AuthorityStoreProviderKind;
export type LocalAuthorityProviderKind = "file" | "sqlite" | "postgresql";
export type LocalAuthoritySource = Extract<AuthorityStoreSourceAuthority,
  "file_v0" | "sqlite_v0" | "postgresql_v0">;
type ProviderOpenReason =
  | "local_authority_selector_unavailable"
  | "local_authority_selector_invalid"
  | "local_authority_selector_missing"
  | "local_authority_provider_unavailable"
  | "local_authority_provider_missing"
  | "local_authority_provider_open_failed"
  | "local_authority_provider_identity_mismatch";

/**
 * The selector contains only public binding facts. Credentials and database
 * clients stay in the service-owned factory supplied by the caller.
 */
export interface LocalPostgreSqlAuthoritySelection {
  schema_version: typeof SCHEMA;
  provider: "postgresql";
  goal_id: string;
  tenant_id: string;
  store_identity: string;
}

export type LocalPostgreSqlAuthorityFactory = (
  selection: LocalPostgreSqlAuthoritySelection,
) => Promise<AuthorityStore> | AuthorityStore;

export interface LocalAuthorityProviderDependencies {
  /** Service-owned hook for the medium-term PostgreSQL profile. */
  openPostgresqlStore?: LocalPostgreSqlAuthorityFactory;
}

export interface LocalAuthorityStoreHandle {
  store: AuthorityStore;
  provider: LocalAuthorityProviderKind;
  sourceAuthority: LocalAuthoritySource;
}

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

function sourceFor(provider: LocalAuthorityProviderKind): LocalAuthoritySource {
  return `${provider}_v0` as LocalAuthoritySource;
}

function selectorError(reason: string): LocalAuthorityProviderOpenError {
  return new LocalAuthorityProviderOpenError(null, "local_authority_selector_invalid", reason);
}

function decodePostgreSqlSelection(value: Record<string, unknown>, goalId: string): LocalPostgreSqlAuthoritySelection {
  if (!hasExactAuthorityKeys(value, ["schema_version", "provider", "goal_id", "tenant_id", "store_identity"]) ||
      value.provider !== "postgresql" || typeof value.tenant_id !== "string" ||
      value.tenant_id.trim() !== value.tenant_id || value.tenant_id.length === 0 ||
      typeof value.store_identity !== "string" ||
      !/^postgresql:[0-9a-f]{32}$/.test(value.store_identity)) {
    throw selectorError("Invalid PostgreSQL authority provider selector");
  }
  return {
    schema_version: SCHEMA,
    provider: "postgresql",
    goal_id: goalId,
    tenant_id: requireAuthorityStoreId(value.tenant_id, "PostgreSQL tenant id"),
    store_identity: value.store_identity,
  };
}

async function openSelectedSqlite(root: string, goalId: string, storeIdentity: string): Promise<AuthorityStore> {
  const p = paths(root, goalId);
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
    if (identity.store_identity !== storeIdentity) {
      throw new LocalAuthorityProviderOpenError("sqlite_v0", "local_authority_provider_identity_mismatch", "Selected SQLite authority identity changed");
    }
    // Keep every subsequent operation fenced to the selected lineage.
    return new SqliteAuthorityStore(p.sqlite, goalId, {existingOnly: true, expectedIdentity: storeIdentity});
  } catch (error) {
    if (error instanceof LocalAuthorityProviderOpenError) throw error;
    throw new LocalAuthorityProviderOpenError("sqlite_v0", "local_authority_provider_open_failed", "Selected SQLite authority could not be opened");
  }
}

async function openSelectedPostgreSql(
  selection: LocalPostgreSqlAuthoritySelection,
  dependencies: LocalAuthorityProviderDependencies,
): Promise<AuthorityStore> {
  if (dependencies.openPostgresqlStore === undefined) {
    throw new LocalAuthorityProviderOpenError(
      "postgresql_v0",
      "local_authority_provider_unavailable",
      "PostgreSQL authority requires a service-owned store factory",
    );
  }
  let store: AuthorityStore;
  try {
    store = await dependencies.openPostgresqlStore(selection);
  } catch (error) {
    throw new LocalAuthorityProviderOpenError(
      "postgresql_v0",
      "local_authority_provider_open_failed",
      "Selected PostgreSQL authority could not be opened",
      error instanceof LocalAuthorityProviderOpenError ? error.reasonCode : undefined,
    );
  }
  if (store === null || typeof store !== "object" || authorityStoreSourceAuthority(store) !== "postgresql_v0") {
    throw new LocalAuthorityProviderOpenError(
      "postgresql_v0",
      "local_authority_provider_identity_mismatch",
      "PostgreSQL provider factory returned a different provider",
    );
  }
  let identity;
  try {
    identity = await store.storeIdentity();
  } catch (error) {
    throw new LocalAuthorityProviderOpenError(
      "postgresql_v0",
      "local_authority_provider_open_failed",
      "Selected PostgreSQL authority identity could not be read",
      error instanceof LocalAuthorityProviderOpenError ? error.reasonCode : undefined,
    );
  }
  if (identity.status !== "available") {
    throw new LocalAuthorityProviderOpenError("postgresql_v0", "local_authority_provider_open_failed", identity.reason, identity.reason_code);
  }
  if (identity.store_identity !== selection.store_identity) {
    throw new LocalAuthorityProviderOpenError("postgresql_v0", "local_authority_provider_identity_mismatch", "Selected PostgreSQL authority identity changed");
  }
  return store;
}

export async function openLocalAuthorityStoreHandle(
  root: string,
  goalId: string,
  dependencies: LocalAuthorityProviderDependencies = {},
): Promise<LocalAuthorityStoreHandle> {
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
      if ((error as NodeJS.ErrnoException).code === "ENOENT") {
        return {store: new FileAuthorityStore(p.file, goalId), provider: DEFAULT_LOCAL_AUTHORITY_PROVIDER,
          sourceAuthority: sourceFor(DEFAULT_LOCAL_AUTHORITY_PROVIDER)};
      }
      throw new LocalAuthorityProviderOpenError(null, "local_authority_selector_unavailable", "Local authority selection could not be resolved");
    }
    throw new LocalAuthorityProviderOpenError(null, "local_authority_selector_missing", "SQLite authority exists but its provider selector is missing");
  }
  let config: unknown;
  try { config = JSON.parse(raw); }
  catch { throw new LocalAuthorityProviderOpenError(null, "local_authority_selector_invalid", "Invalid local authority provider selector JSON"); }
  if (!isAuthorityJsonObject(config) || config.schema_version !== SCHEMA || config.goal_id !== goalId ||
      (config.provider !== "sqlite" && config.provider !== "postgresql")) {
    throw selectorError("Invalid local authority provider selector");
  }
  if (config.provider === "sqlite") {
    if (!hasExactAuthorityKeys(config, ["schema_version", "provider", "goal_id", "store_identity"]) ||
        typeof config.store_identity !== "string" || !/^sqlite:[0-9a-f]{32}$/.test(config.store_identity)) {
      throw selectorError("Invalid SQLite authority provider selector");
    }
    const store = await openSelectedSqlite(root, goalId, config.store_identity);
    return {store, provider: "sqlite", sourceAuthority: sourceFor("sqlite")};
  }
  const selection = decodePostgreSqlSelection(config, goalId);
  const store = await openSelectedPostgreSql(selection, dependencies);
  return {store, provider: "postgresql", sourceAuthority: sourceFor("postgresql")};
}

export async function openLocalAuthorityStore(
  root: string,
  goalId: string,
  dependencies: LocalAuthorityProviderDependencies = {},
): Promise<AuthorityStore> {
  return (await openLocalAuthorityStoreHandle(root, goalId, dependencies)).store;
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
