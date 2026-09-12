import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import type {
  AuthorityStore,
  AuthorityStoreCommit,
} from "../../loopx/control_plane/coordination/authority_store.ts";
import {
  FileAuthorityStore,
} from "../../loopx/control_plane/coordination/file_authority_store.ts";
import {
  NoKVAuthorityStore,
  type NoKVBlobCasRequest,
  type NoKVBlobCasResult,
  type NoKVBlobReadResult,
  type NoKVBlobTransport,
  type NoKVStoreIdentityResult,
} from "../../loopx/control_plane/coordination/nokv_authority_store.ts";
import {
  cloneAuthorityTransaction,
  decodeAuthorityTransaction,
  transactionForRevision,
} from "../../loopx/control_plane/coordination/authority_store_transactions.ts";

type MutableRecord = Record<string, unknown>;

interface TransactionFixture {
  name: string;
  expected: "accept" | "reject";
  mutate(transaction: MutableRecord): MutableRecord;
}

const seedCommit: AuthorityStoreCommit = {
  expected_provider_revision: null,
  operation_id: "semantic-fixture",
  events: [{
    type: "fixture_event",
    metadata: { z: "last", a: ["nested", { stable: true }] },
  }],
  next_projection: {
    schema_version: "fixture_projection_v0",
    nested: { z: 2, a: 1 },
  },
  receipts: [{
    operation_id: "semantic-fixture",
    accepted: true,
    details: { z: "last", a: "first" },
  }],
};

function copyRecord(value: MutableRecord): MutableRecord {
  return { ...value };
}

function reverseObjectKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(reverseObjectKeys);
  if (value === null || typeof value !== "object") return value;
  const entries = Object.entries(value as MutableRecord).reverse().map(([key, item]) => [
    key,
    reverseObjectKeys(item),
  ] as const);
  return Object.fromEntries(entries);
}

const transactionFixtures: readonly TransactionFixture[] = [
  {
    name: "native record",
    expected: "accept",
    mutate: copyRecord,
  },
  {
    name: "legacy-compatible record with reordered nested keys",
    expected: "accept",
    mutate: (transaction) => reverseObjectKeys(transaction) as MutableRecord,
  },
  {
    name: "unknown top-level key",
    expected: "reject",
    mutate: (transaction) => ({ ...transaction, stale_metadata: true }),
  },
  {
    name: "malformed receipts list",
    expected: "reject",
    mutate: (transaction) => ({ ...transaction, receipts: "not-an-array" }),
  },
  {
    name: "malformed nested event record",
    expected: "reject",
    mutate: (transaction) => ({ ...transaction, events: [null] }),
  },
  {
    name: "non-string operation identity",
    expected: "reject",
    mutate: (transaction) => ({ ...transaction, operation_id: 7 }),
  },
];

function logicalFixtureTransaction(): MutableRecord {
  return {
    cursor: "1",
    provider_revision: "file:1:fixture",
    operation_id: seedCommit.operation_id,
    events: seedCommit.events,
    projection: seedCommit.next_projection,
    receipts: seedCommit.receipts,
  };
}

function expectedRevisionInput(): MutableRecord {
  return {
    cursor: "1",
    operation_id: seedCommit.operation_id,
    events: seedCommit.events,
    projection: seedCommit.next_projection,
    receipts: seedCommit.receipts,
  };
}

interface FixtureProvider {
  name: string;
  store: AuthorityStore;
  readDocument(): Promise<MutableRecord>;
  writeDocument(document: MutableRecord): Promise<void>;
  cleanup(): Promise<void>;
}

interface FixtureNoKVBackend {
  identity: string;
  blob: { bytes: Uint8Array; generation: number } | null;
}

class FixtureNoKVTransport implements NoKVBlobTransport {
  readonly backend: FixtureNoKVBackend;

  constructor(backend: FixtureNoKVBackend) {
    this.backend = backend;
  }

  async storeIdentity(_workbench: string): Promise<NoKVStoreIdentityResult> {
    return { status: "available", store_identity: this.backend.identity };
  }

  async readBlob(_workbench: string, _path: string): Promise<NoKVBlobReadResult> {
    return this.backend.blob
      ? {
        status: "loaded",
        bytes: this.backend.blob.bytes.slice(),
        generation: this.backend.blob.generation,
      }
      : { status: "missing" };
  }

  async casPublishBlob(request: NoKVBlobCasRequest): Promise<NoKVBlobCasResult> {
    const currentGeneration = this.backend.blob?.generation ?? null;
    if (currentGeneration !== request.expected_generation) {
      return { status: "conflict", current_generation: currentGeneration };
    }
    const generation = (currentGeneration ?? 0) + 1;
    this.backend.blob = { bytes: request.bytes.slice(), generation };
    return { status: "applied", generation };
  }
}

async function seed(store: AuthorityStore): Promise<void> {
  const result = await store.commitAuthority(seedCommit);
  assert.equal(result.status, "applied", JSON.stringify(result));
}

async function createFileProvider(): Promise<FixtureProvider> {
  const root = await mkdtemp(join(tmpdir(), "authority-semantic-file-"));
  const store = new FileAuthorityStore(root, "goal-a");
  await seed(store);
  return {
    name: "file",
    store,
    async readDocument() {
      return JSON.parse(await readFile(store.path, "utf8")) as MutableRecord;
    },
    async writeDocument(document) {
      await writeFile(store.path, JSON.stringify(document));
    },
    cleanup: () => rm(root, { recursive: true, force: true }),
  };
}

async function createNoKVProvider(): Promise<FixtureProvider> {
  const backend: FixtureNoKVBackend = {
    identity: `nokv:authority-workbench:${"a".repeat(32)}`,
    blob: null,
  };
  const store = new NoKVAuthorityStore(new FixtureNoKVTransport(backend), {
    tenant_id: "tenant-a",
    goal_id: "goal-a",
    workbench: "authority-workbench",
  });
  await seed(store);
  return {
    name: "NoKV",
    store,
    async readDocument() {
      assert.ok(backend.blob);
      return JSON.parse(new TextDecoder().decode(backend.blob.bytes)) as MutableRecord;
    },
    async writeDocument(document) {
      assert.ok(backend.blob);
      backend.blob = {
        generation: backend.blob.generation,
        bytes: new TextEncoder().encode(JSON.stringify(document)),
      };
    },
    async cleanup() {},
  };
}

const providerFactories: readonly [string, () => Promise<FixtureProvider>][] = [
  ["file", createFileProvider],
  ["NoKV", createNoKVProvider],
];

test("shared decoder enforces the complex transaction fixture", () => {
  for (const fixture of transactionFixtures) {
    const candidate = fixture.mutate(logicalFixtureTransaction());
    if (fixture.expected === "accept") {
      const decoded = decodeAuthorityTransaction(candidate);
      assert.deepEqual(transactionForRevision(decoded), expectedRevisionInput(), fixture.name);
      assert.equal(decoded.provider_revision, "file:1:fixture", fixture.name);
    } else {
      assert.throws(() => decodeAuthorityTransaction(candidate), fixture.name);
    }
  }
});

test("file and NoKV providers share fixture acceptance and revision projection", async (t) => {
  for (const fixture of transactionFixtures) {
    await t.test(fixture.name, async () => {
      for (const [, createProvider] of providerFactories) {
        const provider = await createProvider();
        try {
          const baseline = await provider.readDocument();
          const baselineTransaction = baseline.committed as MutableRecord[];
          baselineTransaction[0] = fixture.mutate(baselineTransaction[0]!);
          await provider.writeDocument(baseline);
          const loaded = await provider.store.loadAuthority();
          if (fixture.expected === "accept") {
            assert.equal(loaded.status, "loaded", `${provider.name}: ${JSON.stringify(loaded)}`);
            if (loaded.status === "loaded") {
              assert.equal(loaded.cursor, "1");
              assert.equal(loaded.provider_revision, baseline.provider_revision as string);
            }
          } else {
            assert.equal(loaded.status, "failed", `${provider.name}: ${JSON.stringify(loaded)}`);
            if (loaded.status === "failed") {
              assert.equal(loaded.reason_code, "provider_protocol_violation");
            }
          }
        } finally {
          await provider.cleanup();
        }
      }
    });
  }
});

test("file and NoKV scan results are isolated clones", async (t) => {
  for (const [name, createProvider] of providerFactories) {
    await t.test(name, async () => {
      const provider = await createProvider();
      try {
        const first = await provider.store.scanCommitted(null, 10);
        assert.equal(first.status, "page");
        if (first.status !== "page") return;
        const firstTransaction = first.transactions[0]!;
        (firstTransaction.projection as MutableRecord).mutated = true;
        (firstTransaction.events as MutableRecord[]).push({ leaked: true });
        const second = await provider.store.scanCommitted(null, 10);
        assert.equal(second.status, "page");
        if (second.status !== "page") return;
        assert.equal((second.transactions[0]!.projection as MutableRecord).mutated, undefined);
        assert.equal(second.transactions[0]!.events.length, 1);
      } finally {
        await provider.cleanup();
      }
    });
  }
});

test("transaction clone preserves the canonical logical projection", () => {
  const decoded = decodeAuthorityTransaction(logicalFixtureTransaction());
  const cloned = cloneAuthorityTransaction(decoded);
  assert.deepEqual(transactionForRevision(cloned), expectedRevisionInput());
  (cloned.projection as MutableRecord).changed = true;
  assert.equal((decoded.projection as MutableRecord).changed, undefined);
});
